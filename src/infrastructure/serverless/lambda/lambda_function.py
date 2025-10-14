# src/infrastructure/serverless/lambda/lambda_function.py

import json
import os
import boto3
import logging

# --- ロガー設定 ---
# CloudWatch Logsに適切に出力するために、ハンドラ外で設定するのが推奨
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- 環境変数から設定値を取得 ---
# Lambda関数の設定で環境変数を設定してください
try:
    SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
    EXPECTED_SECRET = os.environ['SECRET_PHRASE']
except KeyError as e:
    logger.error(f"環境変数が設定されていません: {e}")
    # 環境変数がない場合は致命的な設定エラーなので、ここで処理を停止させるか、
    # デフォルト値を設定するなどの対応が必要。ここではエラーログのみ。
    SQS_QUEUE_URL = None
    EXPECTED_SECRET = None

# --- SQSクライアント初期化 ---
sqs_client = boto3.client('sqs')

# --- Lambdaハンドラ関数 ---
def lambda_handler(event, context):
    """
    API GatewayからのPOSTリクエストを処理し、SQSにメッセージを送信するLambda関数
    """
    logger.info(f"受信イベント: {json.dumps(event)}") # デバッグ用にイベント全体をログ出力

    # --- 環境変数チェック ---
    if not SQS_QUEUE_URL or not EXPECTED_SECRET:
        logger.error("SQS_QUEUE_URL または SECRET_PHRASE 環境変数が設定されていません。")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error: Configuration missing.'})
        }

    # --- リクエストボディの取得と解析 ---
    try:
        # API Gateway (HTTP API) のペイロード v2.0 形式を想定
        # REST API や ペイロード v1.0 の場合は event['body'] の形式が異なる可能性あり
        if 'body' not in event:
            raise ValueError("リクエストボディが見つかりません。")

        body_str = event['body']
        payload = json.loads(body_str)
        logger.info(f"受信ペイロード: {json.dumps(payload)}")

    except json.JSONDecodeError:
        logger.error("リクエストボディのJSON解析に失敗しました。")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON format in request body.'})
        }
    except ValueError as e:
        logger.error(str(e))
        return {
            'statusCode': 400,
            'body': json.dumps({'message': str(e)})
        }
    except Exception as e:
        logger.error(f"ペイロード取得・解析中に予期せぬエラー: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error during payload processing.'})
        }

    # --- 簡易認証 ---
    received_secret = payload.get('secret')
    if received_secret != EXPECTED_SECRET:
        logger.warning(f"不正なSecretを受信: {received_secret}")
        return {
            'statusCode': 401, # Unauthorized
            'body': json.dumps({'message': 'Authentication failed.'})
        }
    logger.info("Secret認証成功")

    # --- 必須パラメータの検証 (例) ---
    # 設計したメッセージ形式に合わせて必要なキーをチェック
    required_keys = [
        'symbol', 'order_action', 'order_type', 'lot_size'
        # シナリオ注文やポジション管理のパラメータも必要に応じて追加
    ]
    missing_keys = [key for key in required_keys if key not in payload]
    if missing_keys:
        logger.error(f"必須パラメータが不足しています: {missing_keys}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': f'Missing required parameters: {missing_keys}'})
        }
    logger.info("必須パラメータ検証完了")

    # --- SQSメッセージ送信 ---
    try:
        # メッセージボディとしてペイロード全体を送信（secretは含めても良いが、不要なら除外も可）
        # 不要なキーを除外する場合:
        # message_payload = {k: v for k, v in payload.items() if k != 'secret'}
        # message_body = json.dumps(message_payload)
        message_body = json.dumps(payload) # ここでは簡単のため全体を送信

        logger.info(f"SQSキュー ({SQS_QUEUE_URL}) にメッセージを送信します: {message_body}")

        response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_body
            # 標準キューなので MessageGroupId や MessageDeduplicationId は不要
        )

        logger.info(f"SQS送信成功: MessageId={response.get('MessageId')}")

        # --- 成功レスポンス ---
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Order request received successfully.',
                'sqs_message_id': response.get('MessageId')
            })
        }

    except Exception as e:
        logger.error(f"SQSへのメッセージ送信中にエラーが発生しました: {e}")
        # boto3 のクライアントエラーなどもここでキャッチされる
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error during SQS message sending.'})
        }