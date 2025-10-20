# src/application/use_cases/order_processing/process_sqs_order.py
import json
import logging
import MetaTrader5 as mt5
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone

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
            
            # MT5注文実行（新規注文 or 決済注文）
            if mt5_connected_flag:
                order_action = payload.get('order_action', '').upper()
                
                if order_action == 'CLOSE':
                    # 決済処理（SQS統一アーキテクチャ）
                    order_success_flag, order_result_obj = self._execute_close_order(payload, credentials)
                else:
                    # 新規注文処理
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
    
    def _execute_close_order(self, payload: Dict[str, Any], credentials: Dict[str, Any]) -> Tuple[bool, Optional[Any]]:
        """
        ポジション決済処理（SQS統一アーキテクチャ）
        
        Args:
            payload: CLOSE注文ペイロード
                {
                    'order_action': 'CLOSE',
                    'mt5_ticket': int,
                    'lot_size': float,
                    'symbol': str,
                    'comment': str
                }
            credentials: MT5認証情報
        
        Returns:
            Tuple[bool, Any]: (成功フラグ, 決済結果)
        """
        try:
            mt5_ticket = payload.get('mt5_ticket')
            lot_size = payload.get('lot_size')
            symbol = payload.get('symbol', '')
            comment = payload.get('comment', 'TSS_Close_Order')
            
            logger.info(f"Processing CLOSE order: ticket={mt5_ticket}, volume={lot_size}, symbol={symbol}")
            
            # MT5PositionProviderを使用して決済
            from src.infrastructure.di.container import container
            position_provider = container.get_mt5_position_provider()
            position_repository = container.get_position_repository()
            
            # 1. 既存ポジションをDynamoDBに記録（初回の場合）
            existing_position = position_repository.find_by_mt5_ticket(mt5_ticket)
            if not existing_position:
                # MT5からポジション情報を取得してDynamoDBに保存
                mt5_position_info = position_provider.get_position_by_ticket(mt5_ticket)
                if mt5_position_info:
                    # MT5データからPosition Entity作成
                    from src.domain.entities.position import Position
                    position_entity = Position.from_mt5_position(mt5_position_info)
                    position_repository.save(position_entity)
                    logger.info(f"Position saved to DynamoDB before close: {position_entity.position_id}")
            
            # 2. MT5で決済実行
            success, error_msg = position_provider.close_position(
                ticket=mt5_ticket,
                volume=lot_size
            )
            
            if success:
                # 3. DynamoDB のポジション状態を CLOSED に更新
                if existing_position or position_repository.find_by_mt5_ticket(mt5_ticket):
                    close_data = {
                        'closed_at': datetime.now(timezone.utc).isoformat(),
                        'realized_pnl': str(existing_position.unrealized_pnl) if existing_position else '0'
                    }
                    position_repository.update_status(mt5_ticket, 'CLOSED', close_data)
                    logger.info(f"Position status updated to CLOSED in DynamoDB: {mt5_ticket}")
                
                logger.info(f"CLOSE order executed successfully: ticket={mt5_ticket}")
                
                # 4. 結果オブジェクト作成（既存のorder_repositoryと互換性）
                result_obj = type('CloseResult', (), {
                    'order': mt5_ticket,
                    'retcode': 10009,  # TRADE_RETCODE_DONE
                    'comment': f'Position closed: {comment}',
                    'request': type('CloseRequest', (), {
                        'symbol': symbol,
                        'volume': lot_size,
                        'type': 'CLOSE',
                        'action': 'CLOSE',
                        'comment': comment
                    })()
                })()
                
                return True, result_obj
                
            else:
                logger.error(f"CLOSE order failed: {error_msg}")
                return False, None
                
        except Exception as e:
            logger.error(f"Exception during CLOSE order execution: {e}", exc_info=True)
            return False, None