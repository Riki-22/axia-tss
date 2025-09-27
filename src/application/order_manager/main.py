# C:\trading_strategy_system\src\order_manager\main.py

import time
import logging

from config_loader import QUEUE_URL, sqs_client
from message_processor import process_message

logger = logging.getLogger(__name__)

def main_loop():
    """SQSキューを継続的にポーリングするメインループ"""
    if not QUEUE_URL :
        logger.error("SQSキューURLが正しく設定されていません。config_loader.pyを確認してください。")
        return
    if not sqs_client:
        logger.error("SQSクライアントが初期化されていません。config_loader.pyを確認してください。")
        return

    logger.info(f"Order Manager起動。キュー ({QUEUE_URL}) のポーリングを開始...")
    while True:
        try:
            # SQSからメッセージを受信 (ロングポーリング: 最大20秒待機)
            # VisibilityTimeout はSQSキュー側で設定 (デフォルト30秒)
            # receive_messageのVisibilityTimeoutで一時的に上書きも可能
            response = sqs_client.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,    # 一度に処理するメッセージ数 (まずは1で)
                WaitTimeSeconds=20,       # ロングポーリング設定
                AttributeNames=['All'],   # メッセージ属性も取得する場合 (任意)
                MessageAttributeNames=['All'] # メッセージ属性も取得する場合 (任意)
            )

            if 'Messages' in response:
                message = response['Messages'][0]
                receipt_handle = message['ReceiptHandle'] # メッセージ削除時に必要

                logger.info("-" * 40) # メッセージ処理の区切り
                # メッセージ処理関数を呼び出し
                should_delete = process_message(message)

                # 処理結果に基づいてメッセージを削除
                if should_delete:
                    try:
                        sqs_client.delete_message(
                            QueueUrl=QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        logger.info(f"メッセージ削除完了: {message['MessageId']}")
                    except Exception as e:
                        # メッセージ削除失敗はクリティカルではないことが多いがログは出す
                        logger.error(f"メッセージ削除中にエラー: {e}", exc_info=True)
                else:
                    # 処理失敗（リトライさせたい場合）は削除しない
                    logger.warning(f"メッセージ処理失敗、削除スキップ: {message['MessageId']}")
                logger.info("-" * 40)

            else:
                # メッセージがない場合 (WaitTimeSecondsの間待機した結果)
                logger.debug("受信メッセージなし。ポーリング継続...")
                # CPU負荷を少し下げるために短いsleepを入れても良い (オプション)
                # time.sleep(1)

        except KeyboardInterrupt: # Ctrl+C で停止した場合
            logger.info("停止シグナル受信。メインループを終了します。")
            break
        except Exception as e: # ループ中の予期せぬエラー
            logger.critical(f"メインループで致命的なエラーが発生: {e}", exc_info=True)
            logger.info("60秒待機して処理を継続します...")
            time.sleep(60) # 予期せぬエラー発生時は少し待つ

if __name__ == "__main__":
    main_loop()