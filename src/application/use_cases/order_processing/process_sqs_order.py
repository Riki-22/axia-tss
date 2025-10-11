# src/application/use_cases/order_processing/process_sqs_order.py
import json
import logging
import MetaTrader5 as mt5
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

class ProcessSQSOrderUseCase:
    """SQSメッセージ処理ユースケース"""
    
    def __init__(
        self, 
        kill_switch_repository,
        mt5_connection,
        mt5_order_executor,
        settings
    ):
        self.kill_switch_repository = kill_switch_repository
        self.mt5_connection = mt5_connection
        self.mt5_order_executor = mt5_order_executor
        self.settings = settings
        
    def execute(self, message: Dict[str, Any]) -> bool:
        """
        SQSメッセージを処理するメインロジック
        Returns: bool - メッセージを削除するかどうか
        """
        logger.info(f"受信メッセージID: {message['MessageId']}")
        mt5_connected_flag = False
        final_message_processed_status = False
        
        try:
            # キルスイッチ確認
            if self.kill_switch_repository.is_active():
                logger.info("キルスイッチが有効なため、このメッセージの注文処理は行いません。")
                return True  # キルスイッチONならメッセージ削除
            
            # MT5認証情報取得
            credentials = self.settings.get_mt5_credentials()
            if not credentials:
                logger.error("MT5認証情報を取得できませんでした。")
                return True  # 回復不能エラーとしてメッセージ削除
            
            # MT5接続
            if self.mt5_connection.connect():
                mt5_connected_flag = True
                logger.info("MT5接続に成功しました。")
            else:
                logger.error("MT5に接続できませんでした。")
                return True  # 接続失敗も回復不能エラーとしてメッセージ削除
            
            # ペイロード解析
            payload = json.loads(message['Body'])
            logger.info(f"受信ペイロード:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            # MT5注文実行
            if mt5_connected_flag:
                order_success_flag, order_result_obj = self.mt5_order_executor.execute_order(
                    payload, credentials
                )
                
                if order_success_flag and order_result_obj:
                    logger.info(f"ペイロードに基づくMT5注文処理が成功しました: {message['MessageId']}")
                    final_message_processed_status = True
                else:
                    logger.error(f"ペイロードに基づくMT5注文処理が失敗しました: {message['MessageId']}")
                    final_message_processed_status = True  # 処理自体は試みたので削除対象
            
            if final_message_processed_status:
                logger.info(f"メッセージ処理完了 (MessageId: {message['MessageId']})")
            else:
                logger.warning(f"メッセージ処理が完了しなかった可能性があります (MessageId: {message['MessageId']})")
            
            return final_message_processed_status
            
        except json.JSONDecodeError:
            logger.error(f"不正なJSON形式のメッセージを受信: {message['Body']}")
            return True  # 不正なメッセージは削除
        except Exception as e:
            logger.error(f"process_messageのメイン処理中に予期せぬエラーが発生: {e}", exc_info=True)
            return False  # 予期せぬエラーなので削除せずリトライさせる
        finally:
            if mt5_connected_flag:
                mt5.shutdown()
                logger.info("MT5接続を切断しました。")