#!/bin/bash

# ==============================================================================
# AXIA TSS - AWS Resource Verification Script
#
# Description:
#   This script checks the existence and status of key AWS resources deployed
#   by the SAM template for the AXIA Trading Strategy System. It uses the
#   'dev-sso' profile for authentication.
#
# Usage:
#   ./check_resources.sh
#
# ==============================================================================

# --- Configuration ---
PROFILE="dev-sso"
REGION="ap-northeast-1"

# --- Color Codes ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- Helper Function ---
print_header() {
    echo -e "\n${CYAN}======================================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}======================================================================${NC}"
}

# --- Pre-flight Check ---
echo "Checking AWS credentials using profile: $PROFILE..."
if ! aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" > /dev/null; then
    echo -e "\n${YELLOW}Error: Unable to verify AWS credentials.${NC}"
    echo "Please run 'aws sso login --profile $PROFILE' first."
    exit 1
fi
echo -e "${GREEN}Credentials verified successfully.${NC}"

# 1. DynamoDB Table
print_header "1. Verifying DynamoDB Table"
aws dynamodb list-tables \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query "TableNames[?contains(@, 'TSS_DynamoDB_OrderState')]" \
  --output table

# 2. S3 Bucket
print_header "2. Verifying S3 Bucket"
aws s3 ls --profile "$PROFILE" | grep "tss-raw-data"

# 3. SQS Queue
print_header "3. Verifying SQS Queue"
aws sqs list-queues \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query "QueueUrls[?contains(@, 'TSS_OrderRequestQueue')]" \
  --output table

# 4. Lambda Function
print_header "4. Verifying Lambda Function"
aws lambda list-functions \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query "Functions[?contains(FunctionName, 'TSS_AlertIngestionLambda')].FunctionName" \
  --output table

# 5. Secrets Manager
print_header "5. Verifying Secrets in Secrets Manager"
aws secretsmanager list-secrets \
  --profile "$PROFILE" \
  --region "$REGION" \
  --query "SecretList[?contains(Name, 'mt5/axiory') || contains(Name, 'slack/trading-space')].Name" \
  --output table

# 6. EC2 Instance
print_header "6. Verifying EC2 Instance"
aws ec2 describe-instances \
  --profile "$PROFILE" \
  --region "$REGION" \
  --filters "Name=tag:Name,Values='TSS-MT5-Server'" \
  --query "Reservations[].Instances[].[InstanceId, State.Name, PrivateIpAddress, PublicIpAddress]" \
  --output table

# 7. IAM Roles
print_header "7. Verifying IAM Roles"
aws iam list-roles \
  --profile "$PROFILE" \
  --query "Roles[?contains(RoleName, 'TSS')].RoleName" \
  --output table

# 8. ElastiCache Redis Cluster
print_header "8. Verifying ElastiCache Redis Cluster"
# Corrected the command to use --cache-cluster-id
aws elasticache describe-cache-clusters \
  --profile "$PROFILE" \
  --region "$REGION" \
  --cache-cluster-id "tss-market-data-cache" \
  --query "CacheClusters[].[CacheClusterId, CacheClusterStatus, CacheNodeType]" \
  --output table

echo -e "\n${GREEN}Verification script finished.${NC}\n"
