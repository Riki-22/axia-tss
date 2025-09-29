#!/bin/bash

# GSI1作成スクリプト
# force_create_gsi1.sh

TABLE_NAME="TSS_DynamoDB_OrderState"
REGION="ap-northeast-1"
PROFILE="dev-sso"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "GSI1 作成スクリプト"
echo "============================================"
echo ""

# 1. 現状確認
echo -e "${YELLOW}[Step 1]${NC} 現在の状態確認..."

# JSONで取得して確実に判定
GSI_JSON=$(aws dynamodb describe-table \
    --table-name $TABLE_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query "Table.GlobalSecondaryIndexes" \
    --output json 2>/dev/null)

echo "  GSI情報: $GSI_JSON"

if [ "$GSI_JSON" = "null" ]; then
    echo -e "  ${GREEN}✓ GSIは存在しません${NC}"
else
    echo -e "  ${YELLOW}! 既存のGSIが存在します${NC}"
fi

# 2. テーブル状態確認
echo -e "\n${YELLOW}[Step 2]${NC} テーブル状態確認..."

TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name $TABLE_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query "Table.TableStatus" \
    --output text)

echo "  テーブルステータス: $TABLE_STATUS"

# ACTIVEでない場合は待機
while [ "$TABLE_STATUS" != "ACTIVE" ]; do
    echo "  ⏳ テーブルが$TABLE_STATUS状態です。待機中..."
    sleep 10
    TABLE_STATUS=$(aws dynamodb describe-table \
        --table-name $TABLE_NAME \
        --region $REGION \
        --profile $PROFILE \
        --query "Table.TableStatus" \
        --output text)
done

# 3. GSI1作成
echo -e "\n${YELLOW}[Step 3]${NC} GSI1を作成..."
echo "  用途: オープンポジション高速取得"
echo "  インデックス名: GSI1"
echo "  パーティションキー: gs1pk (String)"
echo "  ソートキー: gs1sk (String)"
echo ""

# 作成実行
aws dynamodb update-table \
    --table-name $TABLE_NAME \
    --region $REGION \
    --profile $PROFILE \
    --attribute-definitions \
        AttributeName=gs1pk,AttributeType=S \
        AttributeName=gs1sk,AttributeType=S \
    --global-secondary-index-updates \
    '[{
        "Create": {
            "IndexName": "GSI1",
            "KeySchema": [
                {"AttributeName": "gs1pk", "KeyType": "HASH"},
                {"AttributeName": "gs1sk", "KeyType": "RANGE"}
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "position_id",
                    "symbol",
                    "side",
                    "status",
                    "size",
                    "entry_price",
                    "stop_loss",
                    "take_profit",
                    "current_price",
                    "unrealized_pnl",
                    "created_utc"
                ]
            }
        }
    }]'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}  ✅ GSI1作成コマンドを実行しました${NC}"
else
    echo -e "${RED}  ❌ エラーが発生しました${NC}"
    echo "  詳細なエラーを確認するには、AWSコンソールをチェックしてください"
    exit 1
fi

# 4. 作成状況の監視
echo -e "\n${YELLOW}[Step 4]${NC} GSI1作成状況を監視..."
echo "  （通常5-10分かかります）"

MAX_WAIT=60  # 10分
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    sleep 10
    
    # JSONで取得
    GSI_STATUS_JSON=$(aws dynamodb describe-table \
        --table-name $TABLE_NAME \
        --region $REGION \
        --profile $PROFILE \
        --query "Table.GlobalSecondaryIndexes[?IndexName=='GSI1'].IndexStatus | [0]" \
        --output json 2>/dev/null)
    
    # "ACTIVE"という文字列かチェック
    if [ "$GSI_STATUS_JSON" = '"ACTIVE"' ]; then
        echo -e "\n${GREEN}✅ GSI1が正常にACTIVEになりました！${NC}"
        break
    elif [ "$GSI_STATUS_JSON" = '"CREATING"' ]; then
        echo -n "."
        COUNTER=$((COUNTER + 1))
    elif [ "$GSI_STATUS_JSON" = "null" ]; then
        echo -n "?"  # まだ作成が開始されていない
        COUNTER=$((COUNTER + 1))
    else
        echo -e "\n状態: $GSI_STATUS_JSON"
        COUNTER=$((COUNTER + 1))
    fi
    
    if [ $COUNTER -eq $MAX_WAIT ]; then
        echo -e "\n${YELLOW}⚠️ タイムアウトしました。AWSコンソールで確認してください${NC}"
        break
    fi
done

# 5. 最終確認
echo -e "\n${YELLOW}[Step 5]${NC} 最終確認..."

echo ""
echo "現在のGSI一覧:"
aws dynamodb describe-table \
    --table-name $TABLE_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query "Table.GlobalSecondaryIndexes[*].{Name:IndexName,Status:IndexStatus,Keys:KeySchema[*].AttributeName}" \
    --output table 2>/dev/null || echo "GSI情報を取得できませんでした"

echo ""
echo "============================================"
echo -e "${GREEN}スクリプト完了${NC}"
echo "============================================"
echo ""
