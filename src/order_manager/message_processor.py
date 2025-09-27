# src/ec2/order_manager/message_processor.py

import json
import logging
import MetaTrader5 as mt5 # mt5.shutdown() のために必要

# 各ハンドラモジュールから必要な関数をインポート
from dynamodb_handler import check_kill_switch
from mt5_handler import get_mt5_credentials, connect_to_mt5, execute_mt5_order
# config_loader から直接設定値を使う場合はここに追加 (今回は主に他のハンドラ経由)

logger = logging.getLogger(__name__)

def process_message(message):
    """
    SQSメッセージを処理するメインロジック
    """
    logger.info(f"受信メッセージID: {message['MessageId']}")
    mt5_connected_flag = False
    final_message_processed_status = False # この処理が最終的に成功したかどうかのフラグ

    try:
        # --- キルスイッチ確認 ---
        if check_kill_switch():
            logger.info("キルスイッチが有効なため、このメッセージの注文処理は行いません。")
            return True # キルスイッチONならメッセージ削除

        # --- MT5認証情報取得 ---
        credentials = get_mt5_credentials()
        if not credentials:
            logger.error("MT5認証情報を取得できませんでした。")
            return True # 回復不能エラーとしてメッセージ削除

        # --- MT5接続 ---
        if connect_to_mt5(credentials):
            mt5_connected_flag = True
            logger.info("MT5接続に成功しました。")
        else:
            logger.error("MT5に接続できませんでした。")
            return True # 接続失敗も回復不能エラーとしてメッセージ削除

        payload = json.loads(message['Body'])
        logger.info(f"受信ペイロード:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

        # --- MT5注文実行 ---
        if mt5_connected_flag:
            order_success_flag, order_result_obj = execute_mt5_order(payload, credentials)
            if order_success_flag and order_result_obj:
                logger.info(f"ペイロードに基づくMT5注文処理が成功しました: {message['MessageId']}")
                # store_order_to_dynamodb は execute_mt5_order 内で呼び出される
                final_message_processed_status = True
            else:
                logger.error(f"ペイロードに基づくMT5注文処理が失敗しました: {message['MessageId']}")
                final_message_processed_status = True # 処理自体は試みたので True (削除対象)

        if final_message_processed_status:
            logger.info(f"メッセージ処理完了 (MessageId: {message['MessageId']})")
        else:
            logger.warning(f"メッセージ処理が完了しなかった可能性があります (MessageId: {message['MessageId']})")

        return final_message_processed_status # メッセージを削除するかどうか

    except json.JSONDecodeError:
        logger.error(f"不正なJSON形式のメッセージを受信: {message['Body']}")
        return True # 不正なメッセージは削除
    except Exception as e:
        logger.error(f"process_messageのメイン処理中に予期せぬエラーが発生: {e}", exc_info=True)
        return False # 予期せぬエラーなので削除せずリトライさせる
    finally:
        if mt5_connected_flag:
            mt5.shutdown()
            logger.info("MT5接続を切断しました。")