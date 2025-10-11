# src/infrastructure/gateways/messaging/sqs/queue_listener.py
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class SQSQueueListener:
    """SQSキューリスナー"""
    
    def __init__(self, queue_url: str, sqs_client, process_message_handler: Callable):
        self.queue_url = queue_url
        self.sqs_client = sqs_client
        self.process_message_handler = process_message_handler
        self.running = False
    
    def start_polling(self):
        """SQSキューを継続的にポーリング"""
        if not self.queue_url:
            logger.error("SQSキューURLが正しく設定されていません。")
            return
        if not self.sqs_client:
            logger.error("SQSクライアントが初期化されていません。")
            return
        
        self.running = True
        logger.info(f"Order Manager起動。キュー ({self.queue_url}) のポーリングを開始...")
        
        while self.running:
            try:
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                    AttributeNames=['All'],
                    MessageAttributeNames=['All']
                )
                
                if 'Messages' in response:
                    message = response['Messages'][0]
                    receipt_handle = message['ReceiptHandle']
                    
                    logger.info("-" * 40)
                    # メッセージ処理（ユースケースに委譲）
                    should_delete = self.process_message_handler(message)
                    
                    if should_delete:
                        try:
                            self.sqs_client.delete_message(
                                QueueUrl=self.queue_url,
                                ReceiptHandle=receipt_handle
                            )
                            logger.info(f"メッセージ削除完了: {message['MessageId']}")
                        except Exception as e:
                            logger.error(f"メッセージ削除中にエラー: {e}", exc_info=True)
                    else:
                        logger.warning(f"メッセージ処理失敗、削除スキップ: {message['MessageId']}")
                    logger.info("-" * 40)
                else:
                    logger.debug("受信メッセージなし。ポーリング継続...")
                    
            except KeyboardInterrupt:
                logger.info("停止シグナル受信。メインループを終了します。")
                self.running = False
                break
            except Exception as e:
                logger.critical(f"メインループで致命的なエラーが発生: {e}", exc_info=True)
                logger.info("60秒待機して処理を継続します...")
                time.sleep(60)
    
    def stop(self):
        """ポーリング停止"""
        self.running = False