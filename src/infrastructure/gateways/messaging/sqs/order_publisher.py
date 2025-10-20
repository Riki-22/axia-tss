# src/infrastructure/gateways/messaging/sqs/order_publisher.py

import json
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class SQSOrderPublisher:
    """
    SQS注文送信クラス
    
    責務:
    - Streamlit UIからの注文データをSQSキューに送信
    - 注文データのバリデーション
    - 送信結果の返却
    
    Usage:
        >>> publisher = SQSOrderPublisher(queue_url, sqs_client)
        >>> order_data = {
        ...     'symbol': 'USDJPY',
        ...     'order_action': 'BUY',
        ...     'order_type': 'MARKET',
        ...     'lot_size': 0.1,
        ...     'tp_price': 151.0,
        ...     'sl_price': 149.0,
        ...     'comment': 'Streamlit_Order'
        ... }
        >>> success, message_id = publisher.send_order(order_data)
    """
    
    def __init__(self, queue_url: str, sqs_client):
        """
        初期化
        
        Args:
            queue_url: SQSキューURL（例: https://sqs.ap-northeast-1.amazonaws.com/xxx/TSS_OrderRequestQueue）
            sqs_client: boto3 SQSクライアント
        """
        self.queue_url = queue_url
        self.sqs_client = sqs_client
        logger.info(f"SQSOrderPublisher initialized: queue_url={queue_url}")
    
    def send_order(self, order_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        注文メッセージをSQSに送信
        
        Args:
            order_data: 注文データ辞書
                {
                    'symbol': str,           # 通貨ペア（例: 'USDJPY'）
                    'order_action': str,     # 'BUY' or 'SELL'
                    'order_type': str,       # 'MARKET' or 'LIMIT'
                    'lot_size': float,       # ロット数（例: 0.1）
                    'tp_price': float,       # 利確価格（例: 151.0）
                    'sl_price': float,       # 損切価格（例: 149.0）
                    'comment': str           # コメント（オプション）
                }
        
        Returns:
            Tuple[bool, str]: (成功フラグ, メッセージID or エラーメッセージ)
                - 成功時: (True, "message_id_string")
                - 失敗時: (False, "error_message")
        
        Raises:
            なし（例外は内部でキャッチしてログ記録）
        """
        try:
            # Step 1: バリデーション
            if not self._validate_order_data(order_data):
                error_msg = "Order data validation failed"
                logger.error(f"{error_msg}: {order_data}")
                return False, error_msg
            
            # Step 2: JSON化
            message_body = json.dumps(order_data, ensure_ascii=False)
            
            # Step 3: SQSクライアントチェック
            if self.sqs_client is None:
                # モックモード（AWS接続なし）
                import uuid
                mock_message_id = f"mock-{uuid.uuid4().hex[:16]}"
                
                logger.warning(
                    f"[MOCK MODE] Order would be sent to SQS: "
                    f"{order_data['symbol']} {order_data['order_action']} "
                    f"{order_data['lot_size']} lot"
                )
                logger.info(f"[MOCK MODE] MessageID: {mock_message_id}")
                logger.debug(f"[MOCK MODE] Message body: {message_body}")
                
                return True, mock_message_id
            
            # Step 4: SQS送信（本番モード）
            logger.info(
                f"Sending order to SQS: "
                f"{order_data['symbol']} {order_data['order_action']} "
                f"{order_data['lot_size']} lot"
            )
            
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
            
            # Step 5: 送信結果確認
            message_id = response.get('MessageId')
            
            if message_id:
                logger.info(
                    f"Order sent successfully: MessageId={message_id}, "
                    f"Symbol={order_data['symbol']}, "
                    f"Action={order_data['order_action']}, "
                    f"Lot={order_data['lot_size']}"
                )
                return True, message_id
            else:
                error_msg = "No MessageId returned from SQS"
                logger.error(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"Failed to send order to SQS: {e}"
            logger.error(error_msg, exc_info=True)
            return False, str(e)
    
    def _validate_order_data(self, order_data: Dict[str, Any]) -> bool:
        """
        注文データのバリデーション
        
        Args:
            order_data: 注文データ辞書
        
        Returns:
            bool: バリデーション成功時True
        
        検証項目:
        - 必須フィールドの存在
        - order_actionの値（'BUY' or 'SELL'）
        - order_typeの値（'MARKET' or 'LIMIT'）
        - lot_sizeの範囲（0より大きい）
        - tp_price, sl_priceの妥当性
        """
        # 必須フィールドチェック（CLOSE注文は例外あり）
        order_action = order_data.get('order_action', '').upper()
        
        if order_action == 'CLOSE':
            # CLOSE注文の必須フィールド
            required_fields = [
                'symbol',
                'order_action',
                'order_type',
                'lot_size',
                'mt5_ticket'  # CLOSE注文特有
            ]
        else:
            # 通常注文の必須フィールド
            required_fields = [
                'symbol',
                'order_action', 
                'order_type',
                'lot_size',
                'tp_price',
                'sl_price'
            ]
        
        for field in required_fields:
            if field not in order_data:
                logger.error(f"Missing required field: {field}")
                return False
        
        # order_actionチェック
        if order_data['order_action'] not in ['BUY', 'SELL', 'CLOSE']:
            logger.error(
                f"Invalid order_action: {order_data['order_action']}. "
                f"Must be 'BUY', 'SELL', or 'CLOSE'"
            )
            return False
        
        # order_typeチェック
        if order_data['order_type'] not in ['MARKET', 'LIMIT']:
            logger.error(
                f"Invalid order_type: {order_data['order_type']}. "
                f"Must be 'MARKET' or 'LIMIT'"
            )
            return False
        
        # lot_sizeチェック
        try:
            lot_size = float(order_data['lot_size'])
            if lot_size <= 0:
                logger.error(f"Invalid lot_size: {lot_size}. Must be > 0")
                return False
            if lot_size > 10:  # 最大10ロットに制限
                logger.error(f"lot_size too large: {lot_size}. Max is 10")
                return False
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid lot_size type: {order_data['lot_size']}, {e}")
            return False
        
        # tp_price, sl_priceチェック（CLOSE注文は不要）
        if order_action != 'CLOSE':
            try:
                tp_price = float(order_data['tp_price'])
                sl_price = float(order_data['sl_price'])
                
                if tp_price <= 0 or sl_price <= 0:
                    logger.error(f"Invalid prices: TP={tp_price}, SL={sl_price}")
                    return False
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid price type: {e}")
                return False
        else:
            # CLOSE注文の場合はmt5_ticketをチェック
            try:
                mt5_ticket = int(order_data['mt5_ticket'])
                if mt5_ticket <= 0:
                    logger.error(f"Invalid mt5_ticket: {mt5_ticket}")
                    return False
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid mt5_ticket type: {e}")
                return False
        
        # symbolチェック（空文字でないこと）
        if not order_data['symbol'] or not isinstance(order_data['symbol'], str):
            logger.error(f"Invalid symbol: {order_data['symbol']}")
            return False
        
        logger.debug(f"Order data validation passed: {order_data}")
        return True