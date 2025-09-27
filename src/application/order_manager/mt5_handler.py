# src/ec2/order_manager/mt5_handler.py

import logging
import json
import MetaTrader5 as mt5
from decimal import Decimal

# config_loaderから必要な設定値とクライアントをインポート
from config_loader import (
    MT5_SECRET_NAME, MT5_TERMINAL_PATH, MT5_MAGIC_NUMBER,
    secretsmanager_client # get_mt5_credentials で使用
)
# validatorsから検証関数をインポート
from validators import check_tp_sl_validity
# dynamodb_handlerから保存関数をインポート (execute_mt5_order内で使用)
from dynamodb_handler import store_order_to_dynamodb

logger = logging.getLogger(__name__)

def get_mt5_credentials():
    """Secrets ManagerからMT5認証情報を取得する"""
    if not MT5_SECRET_NAME:
        logger.error("MT5_SECRET_NAME が設定されていません。")
        return None
    if not secretsmanager_client:
        logger.error("SecretsManagerクライアントが初期化されていません。")
        return None
    try:
        logger.info(f"Secrets Manager からシークレット '{MT5_SECRET_NAME}' を取得します...")
        get_secret_value_response = secretsmanager_client.get_secret_value(
            SecretId=MT5_SECRET_NAME
        )
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            if 'mt5_login' in secret and 'mt5_password' in secret and 'mt5_server' in secret:
                logger.info("MT5認証情報の取得成功。")
                logger.info(f"  Login: {secret.get('mt5_login')}")
                logger.info(f"  Server: {secret.get('mt5_server')}")
                return secret
            else:
                logger.error("シークレット内に必要なキー (mt5_login, mt5_password, mt5_server) が見つかりません。")
                return None
        else:
            logger.error("取得したシークレットは SecretString ではありません。")
            return None
    except Exception as e:
        logger.error(f"Secrets Managerからのシークレット取得中にエラー: {e}", exc_info=True)
        return None

def connect_to_mt5(credentials):
    """取得した認証情報を使ってMT5ターミナルに接続する"""
    if not credentials:
        logger.error("MT5接続試行前に認証情報がありません。")
        return False
    login_id = credentials.get('mt5_login')
    password = credentials.get('mt5_password')
    server = credentials.get('mt5_server')
    try:
        login_id = int(login_id)
    except (ValueError, TypeError):
        logger.error(f"SecretsManagerから取得したmt5_loginが有効な数値ではありません: {login_id}")
        return False
    if not login_id or not password or not server:
        logger.error("MT5接続に必要な認証情報 (Login, Password, Server) が不足しています。")
        return False
    if not MT5_TERMINAL_PATH:
        logger.error("MT5_TERMINAL_PATH が設定されていません。")
        return False
    logger.info(f"MT5に接続試行... Login: {login_id}, Server: {server}, Path: {MT5_TERMINAL_PATH}")
    if not mt5.initialize(login=login_id, password=password, server=server, timeout=10000, path=MT5_TERMINAL_PATH):
        error_code = mt5.last_error()
        logger.error(f"MT5 initialize() 失敗: code={error_code[0]}, 説明={error_code[1]}")
        mt5.shutdown()
        return False
    else:
        logger.info("MT5 initialize() 成功。")
        terminal_info = mt5.terminal_info()
        if terminal_info:
            logger.info(f"  接続先ターミナル: {terminal_info.name}, Build: {terminal_info.build}, Path: {terminal_info.path}")
        account_info = mt5.account_info()
        if account_info:
            logger.info(f"  口座情報: Login={account_info.login}, Name={account_info.name}, Currency={account_info.currency}, Balance={account_info.balance:.2f}")
        return True

def execute_mt5_order(payload, mt5_credentials):
    """SQSペイロードに基づいてMT5に注文を送信する"""
    try:
        logger.info("MT5注文実行処理を開始...")
        symbol = payload.get('symbol')
        order_action_str = payload.get('order_action', '').upper()
        order_type_payload = payload.get('order_type', '').upper()
        lot_size = payload.get('lot_size')
        entry_price_payload = payload.get('entry_price') # str, float, or None
        tp_price_payload = payload.get('tp_price')       # str, float, or None
        sl_price_payload = payload.get('sl_price')       # str, float, or None
        comment_from_payload = payload.get('comment', "TSS_Order") # デフォルトコメント設定

        if not all([symbol, order_action_str, order_type_payload, isinstance(lot_size, (int, float))]):
            logger.error(f"注文に必要な基本パラメータが不足または型が不正です: symbol={symbol}, action={order_action_str}, type={order_type_payload}, lot={lot_size}")
            return False, None

        # --- コメント生成ロジックの修正 ---
        login_id_str = str(mt5_credentials.get('mt5_login', ''))
        by_login_suffix = f" by {login_id_str}"
        max_comment_len = 25
        
        # suffixの長さを考慮してペイロードコメントの最大長を決定
        # suffixが長すぎてペイロードコメントの余地がない場合は、suffixのみ、または"TSS by ID"のようにする
        available_len_for_payload_comment = max_comment_len - len(by_login_suffix)
        
        if available_len_for_payload_comment < 1 : # suffixだけで長すぎる場合
            # とりあえず "TSS" とIDの一部など、固定の短いコメントにする
            final_comment = f"TSS_{login_id_str}"[:max_comment_len] # これでも長ければさらに短縮
        else:
            truncated_payload_comment = comment_from_payload[:available_len_for_payload_comment]
            final_comment = f"{truncated_payload_comment}{by_login_suffix}"
        # --- コメント生成ロジックの修正ここまで ---

        request = {
            "symbol": symbol,
            "volume": float(lot_size),
            "deviation": 10, # スリッページ許容ポイント数
            "magic": MT5_MAGIC_NUMBER,
            "comment": final_comment, # ★修正したコメントを使用★
            "type_time": mt5.ORDER_TIME_GTC, # 有効期限 GTC
            "type_filling": mt5.ORDER_FILLING_IOC, # IOC (Immediate Or Cancel) を基本とする (FOKも検討可)
        }

        # 基準価格 (TP/SLチェック用) と注文タイプ固有のパラメータ設定
        reference_price_for_tp_sl = None # Decimal型で保持
        
        if order_type_payload == "MARKET":
            logger.info("MARKET注文タイプを処理します。")
            request["action"] = mt5.TRADE_ACTION_DEAL # MARKET注文は DEAL action
            tick_info = mt5.symbol_info_tick(symbol)
            if not tick_info:
                logger.error(f"{symbol} のTick情報が取得できませんでした (MARKET注文)。")
                return False, None

            if order_action_str == "BUY":
                request["type"] = mt5.ORDER_TYPE_BUY
                if tick_info.ask == 0:
                    logger.error(f"{symbol} の現在ASK価格が取得できませんでした (MARKET注文)。")
                    return False, None
                execution_price = Decimal(str(tick_info.ask))
            elif order_action_str == "SELL":
                request["type"] = mt5.ORDER_TYPE_SELL
                if tick_info.bid == 0:
                    logger.error(f"{symbol} の現在BID価格が取得できませんでした (MARKET注文)。")
                    return False, None
                execution_price = Decimal(str(tick_info.bid))
            else:
                logger.error(f"未対応の order_action: {order_action_str} for MARKET order")
                return False, None
            
            request["price"] = float(execution_price) # MT5はfloatを期待
            reference_price_for_tp_sl = execution_price

            if tp_price_payload is not None or sl_price_payload is not None:
                is_valid_tp_sl, checked_tp, checked_sl = check_tp_sl_validity(
                    order_action_str, 
                    reference_price_for_tp_sl, # Decimal
                    tp_price_payload, 
                    sl_price_payload, 
                    symbol
                )
                if not is_valid_tp_sl: return False, None
                request["tp"] = float(checked_tp) 
                request["sl"] = float(checked_sl) 
                if float(checked_tp) > 0 or float(checked_sl) > 0 : # どちらかが設定されていれば
                    logger.info("MARKET注文にTP/SLを設定します。")
                else: # 両方0.0なら設定なしと同じ
                    logger.info("MARKET注文はTP/SLなしで実行します (妥当性チェックの結果、または元々指定なし)。")
            else:
                request["tp"] = 0.0
                request["sl"] = 0.0
                logger.info("MARKET注文はTP/SLなしで実行します (ペイロードで指定なし)。")

        elif order_type_payload == "IFOCO": # IFOCOは常にpending注文
            logger.info("IFOCO (Pending) 注文タイプを処理します。")
            request["action"] = mt5.TRADE_ACTION_PENDING # Pending注文は PENDING action
            if entry_price_payload is None or tp_price_payload is None or sl_price_payload is None: 
                logger.error(f"IFOCO注文には entry_price, tp_price, sl_price が必須です。entry={entry_price_payload}, tp={tp_price_payload}, sl={sl_price_payload}")
                return False, None
            
            try:
                execution_price = Decimal(str(entry_price_payload))
            except Exception as e: # より広範なエラーをキャッチ
                logger.error(f"IFOCO注文のentry_priceのDecimal変換に失敗: {entry_price_payload}, Error: {e}")
                return False, None

            request["price"] = float(execution_price)
            reference_price_for_tp_sl = execution_price

            tick_info = mt5.symbol_info_tick(symbol)
            if not tick_info or tick_info.ask == 0 or tick_info.bid == 0:
                 logger.error(f"{symbol} の現在Ask/Bid価格が取得できませんでした (IFOCO注文タイプ決定のため)。")
                 return False, None
            current_ask = Decimal(str(tick_info.ask))
            current_bid = Decimal(str(tick_info.bid))

            if order_action_str == "BUY":
                if execution_price < current_ask: request["type"] = mt5.ORDER_TYPE_BUY_LIMIT
                elif execution_price > current_ask: request["type"] = mt5.ORDER_TYPE_BUY_STOP
                else: 
                    logger.warning(f"BUY IFOCOのentry_price({execution_price})が現在Ask価格({current_ask})と同じです。BUY STOPとして扱います。")
                    request["type"] = mt5.ORDER_TYPE_BUY_STOP
            elif order_action_str == "SELL":
                if execution_price > current_bid: request["type"] = mt5.ORDER_TYPE_SELL_LIMIT
                elif execution_price < current_bid: request["type"] = mt5.ORDER_TYPE_SELL_STOP
                else: 
                    logger.warning(f"SELL IFOCOのentry_price({execution_price})が現在Bid価格({current_bid})と同じです。SELL STOPとして扱います。")
                    request["type"] = mt5.ORDER_TYPE_SELL_STOP
            else:
                logger.error(f"未対応の order_action: {order_action_str} for IFOCO order")
                return False, None
            
            is_valid_tp_sl, checked_tp, checked_sl = check_tp_sl_validity(
                order_action_str, 
                reference_price_for_tp_sl, # Decimal
                tp_price_payload, 
                sl_price_payload, 
                symbol
            )
            if not is_valid_tp_sl: return False, None
            request["tp"] = float(checked_tp) 
            request["sl"] = float(checked_sl) 
        else:
            logger.error(f"未定義の order_type: {order_type_payload}")
            return False, None

        logger.info(f"MT5に注文リクエストを送信します: {json.dumps(request, default=str)}")
        result = mt5.order_send(request)

        if result is None:
            error_code = mt5.last_error()
            logger.error(f"mt5.order_send() が None を返しました。MT5エラー: code={error_code[0]}, 説明={error_code[1]}")
            return False, None
        # TRADE_RETCODE_PLACED は未決注文が正常に受け付けられた場合
        elif result.retcode == mt5.TRADE_RETCODE_DONE or result.retcode == mt5.TRADE_RETCODE_PLACED:
            logger.info(f"注文成功/受付: Ticket={result.order}, Price={result.price}, Volume={result.volume}, Comment='{result.comment}', Retcode={result.retcode}")
            # DynamoDBへの保存は呼び出し元(message_processor)ではなく、ここで成功時に行うのが一貫性から見て自然
            if not store_order_to_dynamodb(result, payload, mt5_credentials.get('mt5_login')):
                # 注文は通ったがDB保存失敗。これは潜在的な問題なので警告レベルを上げる
                logger.error(f"注文 (Ticket: {result.order}) はMT5で成功/受付済みですが、DynamoDBへの保存に失敗しました。手動確認が必要です。")
                # ここで False を返すか、限定的な成功として True を返すかは設計判断
                # 注文が通ってしまっているので、True を返しつつエラーログで警告するのが一案
            return True, result
        else:
            logger.error(f"注文失敗: Ticket={result.order}, Comment='{result.comment}', Retcode={result.retcode}, Retcode_External='{result.retcode_external}'")
            logger.error(f"  リクエスト詳細: {result.request}") # result.request は TradeRequest オブジェクト
            error_code = mt5.last_error() # 注文送信直後のエラーコードを取得
            logger.error(f"  MT5 LastError (order_send後): code={error_code[0]}, 説明={error_code[1]}")
            return False, result
    except Exception as e:
        logger.error(f"MT5注文実行処理中に予期せぬエラー: {e}", exc_info=True)
        return False, None