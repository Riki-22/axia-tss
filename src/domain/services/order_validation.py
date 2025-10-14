# src/domain/services/order_validation.py

import logging
from decimal import Decimal, InvalidOperation # Decimal変換エラーを補足するため
from typing import Optional, Tuple

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

class OrderValidationService:
    """注文の検証サービス"""

    @staticmethod
    def check_tp_sl_validity(
        order_action_str: str, 
        reference_price: float, 
        tp_price: Optional[float], 
        sl_price: Optional[float], 
        symbol: str
    ) -> Tuple[bool, Decimal, Decimal]:
        """TP/SL価格の論理的整合性とブローカーの最小ストップレベル幅をチェックする"""
        # TPとSLの両方がNoneの場合はチェック不要で有効 (TP/SLなし注文)
        if tp_price is None and sl_price is None:
            logger.info("TP価格およびSL価格が未指定です。TP/SLなしとして扱います。")
            return True, Decimal("0.0"), Decimal("0.0") # 有効、価格はDecimal('0.0')

        try:
            # reference_price は常に数値であると期待される
            reference_price_val = Decimal(str(reference_price))

            # tp_price, sl_price は None の可能性がある
            tp_price_val = Decimal(str(tp_price)) if tp_price is not None else None
            sl_price_val = Decimal(str(sl_price)) if sl_price is not None else None

        except (InvalidOperation, ValueError) as e: # Decimal変換時のエラーをキャッチ
            logger.error(f"TP/SLまたは基準価格のDecimal変換に失敗: {e}. TP={tp_price}, SL={sl_price}, Ref={reference_price}")
            return False, tp_price, sl_price # 元の値を返す (呼び出し元で型を意識する必要あり)

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"{symbol} のシンボル情報が取得できませんでした。TP/SL妥当性チェック失敗。")
            return False, tp_price_val, sl_price_val

        point_val = Decimal(str(symbol_info.point))
        stops_level_val = int(symbol_info.trade_stops_level)
        min_stop_distance_price = Decimal(stops_level_val) * point_val
        digits = int(symbol_info.digits)

        log_tp = f"{tp_price_val:.{digits}f}" if tp_price_val is not None else "N/A"
        log_sl = f"{sl_price_val:.{digits}f}" if sl_price_val is not None else "N/A"

        logger.info(
            f"TP/SL妥当性チェック開始: Action={order_action_str}, "
            f"RefPrice={reference_price_val:.{digits}f}, TP={log_tp}, SL={log_sl}, "
            f"MinStopDistPoints={stops_level_val}, Point={point_val}, "
            f"MinStopDistPrice={min_stop_distance_price:.{digits}f}"
        )

        if order_action_str.upper() == "BUY":
            if sl_price_val is not None:
                if sl_price_val >= reference_price_val:
                    logger.error(f"BUY注文でSL価格({sl_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})以上です。")
                    return False, tp_price_val, sl_price_val
                if (reference_price_val - sl_price_val) < min_stop_distance_price:
                    logger.error(
                        f"BUY注文でSL価格({sl_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})に近すぎます。"
                        f"最低価格差: {min_stop_distance_price:.{digits}f} (現在差: {(reference_price_val - sl_price_val):.{digits}f})"
                    )
                    return False, tp_price_val, sl_price_val
            if tp_price_val is not None:
                if tp_price_val <= reference_price_val:
                    logger.error(f"BUY注文でTP価格({tp_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})以下です。")
                    return False, tp_price_val, sl_price_val
                if (tp_price_val - reference_price_val) < min_stop_distance_price:
                    logger.error(
                        f"BUY注文でTP価格({tp_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})に近すぎます。"
                        f"最低価格差: {min_stop_distance_price:.{digits}f} (現在差: {(tp_price_val - reference_price_val):.{digits}f})"
                    )
                    return False, tp_price_val, sl_price_val
        elif order_action_str.upper() == "SELL":
            if sl_price_val is not None:
                if sl_price_val <= reference_price_val:
                    logger.error(f"SELL注文でSL価格({sl_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})以下です。")
                    return False, tp_price_val, sl_price_val
                if (sl_price_val - reference_price_val) < min_stop_distance_price:
                    logger.error(
                        f"SELL注文でSL価格({sl_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})に近すぎます。"
                        f"最低価格差: {min_stop_distance_price:.{digits}f} (現在差: {(sl_price_val - reference_price_val):.{digits}f})"
                    )
                    return False, tp_price_val, sl_price_val
            if tp_price_val is not None:
                if tp_price_val >= reference_price_val:
                    logger.error(f"SELL注文でTP価格({tp_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})以上です。")
                    return False, tp_price_val, sl_price_val
                if (reference_price_val - tp_price_val) < min_stop_distance_price:
                    logger.error(
                        f"SELL注文でTP価格({tp_price_val:.{digits}f})が基準価格({reference_price_val:.{digits}f})に近すぎます。"
                        f"最低価格差: {min_stop_distance_price:.{digits}f} (現在差: {(reference_price_val - tp_price_val):.{digits}f})"
                    )
                    return False, tp_price_val, sl_price_val
        else:
            logger.error(f"未対応の order_action '{order_action_str}' のためTP/SL妥当性チェックをスキップ。")
            return False, tp_price_val, sl_price_val

        logger.info("TP/SL価格は（指定されていれば）ブローカーの最小ストップレベルを含め妥当です。")
        # 戻り値の価格はDecimal型またはNoneで返す
        return True, tp_price_val if tp_price_val is not None else Decimal("0.0"), sl_price_val if sl_price_val is not None else Decimal("0.0")