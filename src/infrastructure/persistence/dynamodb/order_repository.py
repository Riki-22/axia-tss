# src/infrastructure/persistence/dynamodb/order_repository.py
import logging
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import MetaTrader5 as mt5
from src.domain.entities.order import Order
from src.domain.repositories.order_repository import IOrderRepository

logger = logging.getLogger(__name__)

class DynamoDBOrderRepository(IOrderRepository):
    """注文管理のDynamoDBリポジトリ実装"""
    
    def __init__(self, table_name: str, dynamodb_resource):
        self.table_name = table_name
        self.dynamodb_resource = dynamodb_resource
        self.table = dynamodb_resource.Table(table_name) if dynamodb_resource else None
    
    def save(self, order: Order) -> bool:
        """注文を保存"""
        try:
            item = order.to_dict()
            self.table.put_item(Item=item)
            logger.info(f"注文 {order.ticket_id} をDynamoDBに保存しました")
            return True
        except Exception as e:
            logger.error(f"注文保存エラー: {e}")
            return False
    
    def save_mt5_result(self, order_result: Any, payload: Dict[str, Any], mt5_login_id: str) -> bool:
        """MT5の注文結果を保存"""
        if not self.table_name:
            logger.error("DYNAMODB_STATE_TABLE_NAME 環境変数が設定されていません。")
            return False
            
        if not order_result or not hasattr(order_result, 'order') or not order_result.order:
            logger.error("無効な注文結果のため、DynamoDBへの保存をスキップします。")
            return False
        
        if not self.table:
            logger.error("DynamoDBクライアントが初期化されていません。")
            return False
        
        try:
            # 既存のstore_order_to_dynamodb()の中身をそのまま持ってくる
            order_ticket = str(order_result.order)
            current_timestamp_iso = datetime.now(timezone.utc).isoformat()
            
            # MT5の注文タイプ整数値を文字列にマッピング
            mt5_order_type_mapping = {
                mt5.ORDER_TYPE_BUY: "MARKET_BUY",
                mt5.ORDER_TYPE_SELL: "MARKET_SELL",
                mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
                mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
                mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
                mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
                mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY_STOP_LIMIT",
                mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL_STOP_LIMIT",
            }
            executed_order_type_str = mt5_order_type_mapping.get(order_result.request.type, "UNKNOWN")

            # is_scenario_order の判定をペイロードの有無で行う
            is_scenario = payload.get('is_scenario_order', False)
            item_to_store = {
                'pk': f"ORDER#{order_ticket}",
                'sk': "METADATA",

                'item_type': "Order",
                
                # --- Core Order Information ---
                'ticket_id': int(order_ticket),
                'internal_order_id': str(uuid.uuid4()),
                'strategy_id': payload.get('strategy_id'), # GSI1用
                'symbol': payload.get('symbol'),          # GSI2, GSI5用
                'order_action': payload.get('order_action', '').upper(), # GSI5用
                'order_status': 'OPEN', # 約定直後はOPEN。GSI1, GSI2, GSI5用
                'order_type_requested': payload.get('order_type', '').upper(),
                'order_type_executed': executed_order_type_str,
                'requested_lot_size': Decimal(str(payload.get('lot_size', '0'))),
                'executed_lot_size': Decimal(str(order_result.volume)),
                'requested_entry_price': Decimal(str(payload.get('entry_price', '0'))),
                'executed_entry_price': Decimal(str(order_result.price)),
                'requested_tp_price': Decimal(str(payload.get('tp_price', '0'))),
                'executed_tp_price': Decimal(str(order_result.request.tp)),
                'requested_sl_price': Decimal(str(payload.get('sl_price', '0'))),
                'executed_sl_price': Decimal(str(order_result.request.sl)),
                
                # --- Timestamps and Versioning ---
                'created_utc': current_timestamp_iso, # GSI1, GSI2, GSI3, GSI5用
                'submitted_utc': current_timestamp_iso,
                'opened_utc': current_timestamp_iso,
                'closed_utc': None,
                'closing_price': None,
                'profit_loss': None,
                'last_updated_utc': current_timestamp_iso,
                'version': 1,

                # --- System and Broker Information ---
                'mt5_retcode': int(order_result.retcode),
                'mt5_comment': order_result.comment,
                'payload_comment': payload.get('comment'),
                'placed_by_login': str(mt5_login_id),
                
                # --- Scenario Order Attributes ---
                'is_scenario_order': is_scenario,
                'scenario_id_ref': payload.get('scenario_id_ref') if is_scenario else None, # GSI4用
                'scenario_status': "ACTIVE" if is_scenario else None, # 約定したのでACTIVE。GSI4用
                'scenario_activate_price_target': Decimal(str(payload.get('scenario_activate_price_target', '0'))) if is_scenario else None,
                'scenario_entry_price_target': Decimal(str(payload.get('scenario_entry_price_target', '0'))) if is_scenario else None,
                'scenario_cancel_price_target': Decimal(str(payload.get('scenario_cancel_price_target', '0'))) if is_scenario else None,

                # --- Position Management Attributes ---
                'enable_add_position': payload.get('enable_add_position', False),
                'add_position_config': payload.get('add_position_config'),
                'current_add_position_level': 0,
                'enable_breakeven': payload.get('enable_breakeven', False),
                'breakeven_status': "ARMED" if payload.get('enable_breakeven', False) else None,
                'breakeven_trigger_price_target': Decimal(str(payload.get('breakeven_trigger_price_target', '0'))),
                'breakeven_sl_target_price': Decimal(str(payload.get('breakeven_sl_target_price', '0'))),
                'enable_trailing_stop': payload.get('enable_trailing_stop', False),
                'trailing_status': "ACTIVE" if payload.get('enable_trailing_stop', False) else None,
                'trailing_start_price_target': Decimal(str(payload.get('trailing_start_price_target', '0'))),
                'trailing_sl_price_current': Decimal(str(order_result.request.sl)), # 初期値はSL
                'trailing_step_pips': Decimal(str(payload.get('trailing_step_pips', '0'))),
                
                # --- Sparse GSI 用の属性 ---
                'unfulfilled_marker': None # この注文は約定済みなので、この属性はセットしない (またはNone)
            }
            
            # None の値を持つ属性をアイテムから削除
            item_to_store_cleaned = {k: v for k, v in item_to_store.items() if v is not None}
            
            self.table.put_item(Item=item_to_store_cleaned)
            logger.info(f"注文情報 (Ticket: {order_ticket}) をDynamoDBに正常に保存しました。")
            return True
            
        except Exception as e:
            logger.error(f"DynamoDBへの注文情報保存中にエラー: {e}", exc_info=True)
            return False
    
    def find_by_ticket_id(self, ticket_id: str) -> Optional[Order]:
        """チケットIDで注文を検索"""
        try:
            response = self.table.get_item(
                Key={'pk': f'ORDER#{ticket_id}', 'sk': 'METADATA'}
            )
            if 'Item' in response:
                # DynamoDBのアイテムからOrderエンティティを復元
                item = response['Item']
                return Order(
                    ticket_id=item['ticket_id'],
                    symbol=item['symbol'],
                    lot_size=Decimal(item['executed_lot_size']),
                    order_type=item['order_type_executed'],
                    action=item['order_action'],
                    status=item['order_status'],
                    mt5_ticket=item.get('ticket_id'),
                    entry_price=Decimal(item['executed_entry_price']) if item.get('executed_entry_price') else None,
                    tp_price=Decimal(item['executed_tp_price']) if item.get('executed_tp_price') else None,
                    sl_price=Decimal(item['executed_sl_price']) if item.get('executed_sl_price') else None,
                )
            return None
        except Exception as e:
            logger.error(f"注文検索エラー: {e}")
            return None
    
    def find_by_status(self, status: str) -> List[Order]:
        """ステータスで注文を検索（GSIを使用）"""
        # TODO: GSI実装が必要
        return []
    
    def update_status(self, ticket_id: str, status: str, mt5_ticket: Optional[int] = None) -> bool:
        """注文ステータスを更新"""
        try:
            update_expr = "SET order_status = :status, last_updated_utc = :updated"
            expr_values = {
                ':status': status,
                ':updated': datetime.now(timezone.utc).isoformat()
            }
            
            if mt5_ticket:
                update_expr += ", mt5_ticket = :mt5_ticket"
                expr_values[':mt5_ticket'] = mt5_ticket
            
            self.table.update_item(
                Key={'pk': f'ORDER#{ticket_id}', 'sk': 'METADATA'},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )
            return True
        except Exception as e:
            logger.error(f"ステータス更新エラー: {e}")
            return False