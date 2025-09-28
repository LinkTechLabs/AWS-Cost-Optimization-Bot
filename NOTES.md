# Notes – Module 9: Cost Optimization Bot

## Topics
- AWS Cost Management
- Serverless Architecture
- Event-Driven Architecture
- Infrastructure as Code (IaC)
- Monitoring and Alerting

## Resources
### Local Development
- Python 3.11
- AWS CLI configured with admin access
- Boto3 SDK

### AWS Commands
```bash
# Test Lambda function
aws lambda invoke --function-name CostOptimizationBot output.txt

# Check CloudWatch logs
aws logs tail /aws/lambda/CostOptimizationBot --follow

# Get SNS topic attributes
aws sns get-topic-attributes --topic-arn arn:aws:sns:REGION:ACCOUNT_ID:CostAlertsTopic
```

**Important Notes**:
- Cost Explorer data can take up to 24 hours to become available
- Budget alerts are processed by AWS Budgets service, not directly by our Lambda
- The Lambda function uses us-east-1 for Cost Explorer API (global endpoint)
- Ensure IAM user has Billing permissions enabled

### Helpful Links
- [AWS Cost Explorer API Reference](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_Operations_AWS_Cost_Explorer_Service.html)
- [AWS Budgets Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [AWS SNS Pricing](https://aws.amazon.com/sns/pricing/)
 
## Notes (my takeaways)
- The integration between AWS Budgets and SNS requires explicit permissions
- Cost Explorer API requires the ce:GetCostAndUsage permission
- The Lambda function is designed to be idempotent
- Environment variables make the function more configurable
- The forecast feature helps in proactive cost management
- The solution is serverless and scales automatically

## Habit-Checkin
### 2025-09-29 01:15 - Project Completion
- **What I did**: 
    - Implemented a cost optimization bot using AWS Lambda, SNS, and EventBridge
    - Set up AWS Budgets with threshold alerts
    - Created IAM roles with least privilege access
    - Scheduled daily cost reports
    - Tested end-to-end functionality
    
- **Blockers**: 
    - Initial permission issues with Cost Explorer API access
    - SNS subscription confirmation required manual intervention
    
- **Next Step**: 
    - Monitor the daily reports for a week
    - Consider adding more detailed cost breakdowns
    - Implement Infrastructure as Code using AWS SAM

## Screenshots
- [SNS Topic Configuration](screenshots/sns-topic.png)
- [AWS Budget Configuration](screenshots/budget-summary.png)
- [Lambda Function Code](screenshots/lambda_code.png)
- [Lambda Environment Variables](screenshots/lambda_env_var.png)
- [IAM Role Permissions](screenshots/iam-role.png)
- [EventBridge Rule](screenshots/eventbridge.png)

## Future Enhancements
1. Add support for multiple AWS accounts using AWS Organizations
2. Implement cost allocation tags for better cost tracking
3. Add Slack/Teams integration in addition to email
4. Create a dashboard using Amazon QuickSight
5. Add anomaly detection for unusual spending patterns
