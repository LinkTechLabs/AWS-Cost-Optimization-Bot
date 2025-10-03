import os, json, datetime, decimal
import boto3
from collections import defaultdict

SNS_ARN = os.environ["TOPIC_ARN"]
BUDGET_LIMIT = float(os.environ.get("BUDGET_LIMIT","25"))
ALERTS = [int(x) for x in os.environ.get("ALERT_THRESHOLDS","80,100").split(",")]
CURRENCY = os.environ.get("CURRENCY","USD")
TOPN = int(os.environ.get("SERVICES_LIMIT","5"))

# CE is a global endpoint (use us-east-1)
ce = boto3.client("ce", region_name="us-east-1")
sns = boto3.client("sns")
budgets = boto3.client("budgets")  # Read-only check (optional)

# --- NEW/UPDATED GLOBAL FILTER ---
# Define the filter to exclude credits, refunds, and taxes (to get gross usage)
GROSS_COST_FILTER = {
    "Not": {
        "Dimensions": {
            "Key": "RECORD_TYPE",
            "Values": ["Credit", "Refund", "Tax"]
        }
    }
}
# ---------------------------------

def _month_bounds_utc(today):
    start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = today  # CE end is exclusive if using DAILY; we'll handle correctly per call
    return start, end

def _fmt(n):
    # Ensure negligible negative numbers are displayed as 0.00
    if n < 0 and abs(n) < 0.01:
        return "0.00"
    return f"{n:,.2f}"

# --- UPDATED: Applies GROSS_COST_FILTER ---
def get_mtd_total(today):
    start, _ = _month_bounds_utc(today)
    end_excl = (today + datetime.timedelta(days=1)).date().isoformat()
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start.date().isoformat(), "End": end_excl},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        Filter=GROSS_COST_FILTER
    )
    amt = float(resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
    return amt

# --- UPDATED: Applies GROSS_COST_FILTER ---
def get_daily_series(today):
    start, _ = _month_bounds_utc(today)
    end_excl = (today + datetime.timedelta(days=1)).date().isoformat()
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start.date().isoformat(), "End": end_excl},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        Filter=GROSS_COST_FILTER
    )
    days = resp["ResultsByTime"]
    series = [(d["TimePeriod"]["Start"], float(d["Total"]["UnblendedCost"]["Amount"])) for d in days]
    return series

# --- UPDATED: Applies GROSS_COST_FILTER ---
def get_top_services(today, topn=5):
    start, _ = _month_bounds_utc(today)
    end_excl = (today + datetime.timedelta(days=1)).date().isoformat()
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start.date().isoformat(), "End": end_excl},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type":"DIMENSION","Key":"SERVICE"}],
        Filter=GROSS_COST_FILTER
    )
    items = []
    for g in resp["ResultsByTime"][0].get("Groups", []):
        svc = g["Keys"][0]
        amt = float(g["Metrics"]["UnblendedCost"]["Amount"])
        if amt > 0:
            items.append((svc, amt))
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:topn]

# --- UPDATED: Applies GROSS_COST_FILTER ---
def get_forecast(today):
    # Forecast Start Date: Must be TOMORROW (exclusive end of current data)
    forecast_start = (today + datetime.timedelta(days=1)).date().isoformat()
    
    # Forecast End Date: Last day of the current month
    month_end = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    forecast_end = month_end.date().isoformat()
    
    resp = ce.get_cost_forecast(
        TimePeriod={"Start": forecast_start, "End": forecast_end},
        Metric="UNBLENDED_COST",
        Granularity="MONTHLY",
        Filter=GROSS_COST_FILTER
    )
    return float(resp["ForecastResultsByTime"][0]["MeanValue"])

def build_report():
    now = datetime.datetime.utcnow()
    mtd = get_mtd_total(now)
    series = get_daily_series(now)
    top = get_top_services(now, TOPN)
    fc = 0.0
    try:
        fc = get_forecast(now)
    except Exception as e:
        print(f"INFO: Cost forecast failed. Error: {e}") 
        fc = 0.0

    # Day-over-day delta (last two points)
    # --- CORRECTED DAILY SPEND LOGIC ---
    yesterday_cost = 0.0
    dod = None
    
    if len(series) >= 2:
        # series[-1][1] is the cost for the last FULL calendar day available (Yesterday)
        # series[-2][1] is the cost for the day before that (Day Before Yesterday)
        yesterday_cost = series[-1][1] 
        day_before_cost = series[-2][1]
        dod = yesterday_cost - day_before_cost
    elif len(series) == 1:
        # Only one day of data available (e.g., first day of month)
        yesterday_cost = series[-1][1]

    # --- END CORRECTED LOGIC ---

    used_pct = (mtd / BUDGET_LIMIT * 100.0) if BUDGET_LIMIT > 0 else 0.0
    crossed = [p for p in ALERTS if used_pct >= p]

    header = f"AWS Cost Daily Brief — {now.strftime('%Y-%m-%d')}"
    lines = [
        header,
        "-"*len(header),
        f"Month-to-date (MTD): {CURRENCY} {_fmt(mtd)}",
        f"Budget: {CURRENCY} {_fmt(BUDGET_LIMIT)}  |  Used: {used_pct:.1f}%"
    ]
    if fc > 0:
        lines.append(f"Forecast (end of month): {CURRENCY} {_fmt(fc)}")
        
    # --- UPDATED REPORT LINE ---
    lines.append(f"Yesterday's spend: {CURRENCY} {_fmt(yesterday_cost)}")
    if dod is not None:
        lines.append(f"Change vs. Day Prior: {CURRENCY} {_fmt(dod)}")
    # -----------------------------

    if top:
        lines.append("\nTop services this month (Gross Usage):")
        for svc, amt in top:
            lines.append(f"  • {svc}: {CURRENCY} {_fmt(amt)}")

    if crossed:
        lines.append(f"\n⚠️ Budget thresholds crossed: {', '.join(str(x)+'%' for x in crossed)}")

    return "\n".join(lines), crossed

def lambda_handler(event, context):
    body, crossed = build_report()
    subj = "[COST] Daily Brief"
    if crossed:
        subj = f"[COST ALERT ≥{max(crossed)}%] Daily Brief"
    sns.publish(TopicArn=SNS_ARN, Subject=subj, Message=body)
    return {"statusCode": 200, "body": json.dumps({"ok": True, "alert": crossed})}