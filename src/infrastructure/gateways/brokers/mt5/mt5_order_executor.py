# src/infrastructure/gateways/brokers/mt5/mt5_order_executor.py
import logging
import json
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any

# MT5は条件付きインポート
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    # 警告は環境変数で制御
    import os
    if os.getenv('DEBUG', '').lower() == 'true':
        logging.warning("MetaTrader5 module not available. MT5 features will be disabled.")

logger = logging.getLogger(__name__)

class MT5OrderExecutor:
    """MT5注文実行クラス"""
    
    def __init__(self, connection: 'MT5Connection', validation_service: 'OrderValidationService', 
                 order_repository: 'DynamoDBOrderRepository', magic_number: int = 12345):
        self.connection = connection
        self.validation_service = validation_service
        self.order_repository = order_repository
        self.magic_number = magic_number
    
    def execute_order(self, payload: Dict[str, Any], mt5_credentials: Dict[str, Any]) -> Tuple[bool, Optional[Any]]:
        """SQSペイロードに基づいてMT5に注文を送信する"""

        try:
            # 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5が接続されていません")
                return False, None

            logger.info("MT5注文実行処理を開始...")
            symbol = payload.get('symbol')
            order_action_str = payload.get('order_action', '').upper()
            order_type_payload = payload.get('order_type', '').upper()
            lot_size = payload.get('lot_size')
            entry_price_payload = payload.get('entry_price')
            tp_price_payload = payload.get('tp_price')
            sl_price_payload = payload.get('sl_price')
            comment_from_payload = payload.get('comment', "TSS_Order")

            if not all([symbol, order_action_str, order_type_payload, isinstance(lot_size, (int, float))]):
                logger.error(f"注文に必要な基本パラメータが不足または型が不正です")
                return False, None

            # コメント生成（既存ロジック維持）
            login_id_str = str(mt5_credentials.get('mt5_login', ''))
            by_login_suffix = f" by {login_id_str}"
            max_comment_len = 25
            
            available_len_for_payload_comment = max_comment_len - len(by_login_suffix)
            
            if available_len_for_payload_comment < 1:
                final_comment = f"TSS_{login_id_str}"[:max_comment_len]
            else:
                truncated_payload_comment = comment_from_payload[:available_len_for_payload_comment]
                final_comment = f"{truncated_payload_comment}{by_login_suffix}"

            request = {
                "symbol": symbol,
                "volume": float(lot_size),
                "deviation": 10,
                "magic": self.magic_number,
                "comment": final_comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # 基準価格とパラメータ設定
            reference_price_for_tp_sl = None
            
            if order_type_payload == "MARKET":
                logger.info("MARKET注文タイプを処理します。")
                request["action"] = mt5.TRADE_ACTION_DEAL
                tick_info = mt5.symbol_info_tick(symbol)
                if not tick_info:
                    logger.error(f"{symbol} のTick情報が取得できませんでした")
                    return False, None

                if order_action_str == "BUY":
                    request["type"] = mt5.ORDER_TYPE_BUY
                    if tick_info.ask == 0:
                        logger.error(f"{symbol} の現在ASK価格が取得できませんでした")
                        return False, None
                    execution_price = Decimal(str(tick_info.ask))
                elif order_action_str == "SELL":
                    request["type"] = mt5.ORDER_TYPE_SELL
                    if tick_info.bid == 0:
                        logger.error(f"{symbol} の現在BID価格が取得できませんでした")
                        return False, None
                    execution_price = Decimal(str(tick_info.bid))
                else:
                    logger.error(f"未対応の order_action: {order_action_str}")
                    return False, None
                
                request["price"] = float(execution_price)
                reference_price_for_tp_sl = execution_price

                # TP/SL検証
                if tp_price_payload is not None or sl_price_payload is not None:
                    is_valid_tp_sl, checked_tp, checked_sl = self.validation_service.check_tp_sl_validity(
                        order_action_str, 
                        reference_price_for_tp_sl,
                        tp_price_payload, 
                        sl_price_payload, 
                        symbol
                    )
                    if not is_valid_tp_sl: 
                        return False, None
                    request["tp"] = float(checked_tp) 
                    request["sl"] = float(checked_sl)
                else:
                    request["tp"] = 0.0
                    request["sl"] = 0.0

            elif order_type_payload == "IFOCO":
                logger.info("IFOCO (Pending) 注文タイプを処理します。")
                request["action"] = mt5.TRADE_ACTION_PENDING
                
                if entry_price_payload is None or tp_price_payload is None or sl_price_payload is None:
                    logger.error(f"IFOCO注文には entry_price, tp_price, sl_price が必須です")
                    return False, None
                
                try:
                    execution_price = Decimal(str(entry_price_payload))
                except Exception as e:
                    logger.error(f"entry_priceのDecimal変換に失敗: {e}")
                    return False, None

                request["price"] = float(execution_price)
                reference_price_for_tp_sl = execution_price

                # 現在価格を取得して注文タイプを決定
                tick_info = mt5.symbol_info_tick(symbol)
                if not tick_info or tick_info.ask == 0 or tick_info.bid == 0:
                    logger.error(f"{symbol} の現在Ask/Bid価格が取得できませんでした")
                    return False, None
                    
                current_ask = Decimal(str(tick_info.ask))
                current_bid = Decimal(str(tick_info.bid))

                if order_action_str == "BUY":
                    if execution_price < current_ask:
                        request["type"] = mt5.ORDER_TYPE_BUY_LIMIT
                    elif execution_price > current_ask:
                        request["type"] = mt5.ORDER_TYPE_BUY_STOP
                    else:
                        logger.warning(f"entry_priceが現在Ask価格と同じです。BUY STOPとして扱います")
                        request["type"] = mt5.ORDER_TYPE_BUY_STOP
                elif order_action_str == "SELL":
                    if execution_price > current_bid:
                        request["type"] = mt5.ORDER_TYPE_SELL_LIMIT
                    elif execution_price < current_bid:
                        request["type"] = mt5.ORDER_TYPE_SELL_STOP
                    else:
                        logger.warning(f"entry_priceが現在Bid価格と同じです。SELL STOPとして扱います")
                        request["type"] = mt5.ORDER_TYPE_SELL_STOP
                else:
                    logger.error(f"未対応の order_action: {order_action_str}")
                    return False, None
                
                # TP/SL検証
                is_valid_tp_sl, checked_tp, checked_sl = self.validation_service.check_tp_sl_validity(
                    order_action_str, 
                    reference_price_for_tp_sl,
                    tp_price_payload, 
                    sl_price_payload, 
                    symbol
                )
                if not is_valid_tp_sl:
                    return False, None
                request["tp"] = float(checked_tp) 
                request["sl"] = float(checked_sl)
            else:
                logger.error(f"未定義の order_type: {order_type_payload}")
                return False, None

            # 注文送信
            logger.info(f"MT5に注文リクエストを送信します: {json.dumps(request, default=str)}")
            result = mt5.order_send(request)

            if result is None:
                error_code = mt5.last_error()
                logger.error(f"mt5.order_send() が None を返しました。MT5エラー: {error_code}")
                return False, None
            elif result.retcode == mt5.TRADE_RETCODE_DONE or result.retcode == mt5.TRADE_RETCODE_PLACED:
                logger.info(f"注文成功/受付: Ticket={result.order}, Price={result.price}")

                # DynamoDBへの保存（例外をキャッチして注文成功は保証）
                try:
                    if not self.order_repository.save_mt5_result(result, payload, mt5_credentials.get('mt5_login')):
                        logger.error(f"注文 (Ticket: {result.order}) はMT5で成功/受付済みですが、DynamoDBへの保存に失敗しました")
                except Exception as e:
                    logger.error(f"注文 (Ticket: {result.order}) はMT5で成功/受付済みですが、DynamoDBへの保存中に例外発生: {e}", exc_info=True)

                return True, result
            else:
                logger.error(f"注文失敗: Retcode={result.retcode}, Comment={result.comment}")
                return False, result
                
        except Exception as e:
            logger.error(f"MT5注文実行処理中に予期せぬエラー: {e}", exc_info=True)
            return False, None