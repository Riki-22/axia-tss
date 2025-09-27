# src/ec2/order_manager/dynamodb_handler.py

import logging
import json
from datetime import datetime, timezone
from decimal import Decimal
import MetaTrader5 as mt5
import uuid

# config_loaderから必要な設定値とクライアントをインポート
from config_loader import DYNAMODB_STATE_TABLE_NAME, dynamodb_resource

logger = logging.getLogger(__name__)

def check_kill_switch():
    """DynamoDBからキルスイッチの状態を確認する (詳細設計スキーマ対応版)"""
    if not DYNAMODB_STATE_TABLE_NAME:
        logger.error("DYNAMODB_STATE_TABLE_NAME 環境変数が設定されていません。安全のためキルスイッチONとして扱います。")
        return True

    if not dynamodb_resource:
        logger.error("DynamoDBクライアントが初期化されていません。安全のためキルスイッチONとして扱います。")
        return True
    try:
        table = dynamodb_resource.Table(DYNAMODB_STATE_TABLE_NAME)
        # 詳細設計に基づいたキーでキルスイッチアイテムを取得
        key = {'pk': 'GLOBALCONFIG', 'sk': 'SETTING#KILL_SWITCH'}
        logger.info(f"DynamoDBテーブル '{DYNAMODB_STATE_TABLE_NAME}' からキルスイッチの状態を取得します... Key: {key}")
        
        response = table.get_item(Key=key)
        
        if 'Item' in response:
            item = response['Item']
            logger.info(f"キルスイッチアイテムが見つかりました: {item}")
            item_status = item.get('status')
            if item_status == 'ON':
                logger.warning("グローバルキルスイッチがONです。注文関連処理をスキップします。")
                return True
            elif item_status == 'OFF':
                logger.info("グローバルキルスイッチはOFFです。処理を継続します。")
                return False
            else:
                logger.warning(f"'kill_switch' アイテムの 'status' 属性が無効な値('{item_status}')です。安全のため注文処理をスキップします。")
                return True
        else:
            logger.warning(f"'kill_switch' アイテム (pk: GLOBALCONFIG, sk: SETTING#KILL_SWITCH) が見つかりません。安全のため注文処理をスキップします。")
            return True
    except Exception as e:
        logger.error(f"DynamoDBからのキルスイッチ状態取得中にエラー: {e}", exc_info=True)
        return True

def store_order_to_dynamodb(order_result, payload, mt5_login_id):
    """MT5の注文結果とペイロード情報を詳細設計スキーマに基づいてDynamoDBに保存する"""
    if not DYNAMODB_STATE_TABLE_NAME:
        logger.error("DYNAMODB_STATE_TABLE_NAME 環境変数が設定されていません。注文情報を保存できません。")
        return False
    if not order_result or not hasattr(order_result, 'order') or not order_result.order:
        logger.error("無効な注文結果のため、DynamoDBへの保存をスキップします。")
        return False

    if not dynamodb_resource:
        logger.error("DynamoDBクライアントが初期化されていません。注文情報を保存できません。")
        return False
        
    try:
        table = dynamodb_resource.Table(DYNAMODB_STATE_TABLE_NAME)
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
            # --- Primary Key and Item Type (単一テーブル設計のコア) ---
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
        
        logger.info(f"DynamoDBテーブル '{DYNAMODB_STATE_TABLE_NAME}' に詳細な注文情報を保存します...")
        table.put_item(Item=item_to_store_cleaned)
        logger.info(f"注文情報 (Ticket: {order_ticket}) をDynamoDBに正常に保存しました。")
        return True

    except Exception as e:
        logger.error(f"DynamoDBへの注文情報保存中にエラー: {e}", exc_info=True)
        return False
