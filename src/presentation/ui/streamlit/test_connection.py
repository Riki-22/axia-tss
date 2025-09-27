"""DynamoDB接続テスト"""
from services.dynamodb_service import DynamoDBService

# サービスの初期化
db_service = DynamoDBService()

# 接続テスト
print("=== DynamoDB接続テスト ===")
conn_result = db_service.test_connection()
print(f"接続状態: {conn_result['status']}")
if conn_result['status'] == 'SUCCESS':
    print(f"テーブル: {conn_result['table']}")
else:
    print(f"エラー: {conn_result.get('error', 'Unknown')}")

# Kill Switch状態確認
print("\n=== Kill Switch状態 ===")
ks_result = db_service.get_kill_switch_status()
print(f"状態: {ks_result['status']}")
print(f"アクティブ: {ks_result['active']}")
if 'last_updated' in ks_result:
    print(f"最終更新: {ks_result['last_updated']}")
