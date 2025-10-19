# src/presentation/ui/streamlit/layouts/header.py

import streamlit as st
import logging
from src.infrastructure.di.container import DIContainer

logger = logging.getLogger(__name__)
container = DIContainer()


def render_header_metrics():
    """ヘッダーメトリクスの表示（リアルタイムMT5データ）"""
    st.markdown("## AXIA - Trading Strategy System -")
    
    # MT5プロバイダー取得
    try:
        account_provider = container.get_mt5_account_provider()
        price_provider = container.get_mt5_price_provider()
    except Exception as e:
        logger.error(f"Failed to initialize MT5 providers: {e}")
        st.error("⚠️ MT5プロバイダーの初期化に失敗しました")
        return
    
    # データ取得
    account_info = account_provider.get_account_info()
    today_pl = account_provider.calculate_today_pl()
    
    # デフォルト通貨ペアの価格取得（例: USDJPY）
    default_symbol = "USDJPY"
    price_info = price_provider.get_current_price(default_symbol)
    
    # システムステータス
    status_cols = st.columns(4)
    
    # 現在価格
    with status_cols[0]:
        if price_info:
            st.metric(
                f"{price_info['symbol']} 価格",
                f"{price_info['ask']:.3f}",
                f"{price_info['spread']:.1f} pips"
            )
        else:
            st.metric("現在価格", "取得中...", None)
    
    # 本日損益（NYクローズ基準）
    with status_cols[1]:
        if today_pl:
            amount = today_pl['amount']
            percentage = today_pl['percentage']
            
            # 色設定
            delta_color = "normal" if amount >= 0 else "inverse"
            
            st.metric(
                "本日損益",
                f"{percentage:+.2f}%",
                f"¥{amount:+,.0f}",
                delta_color=delta_color
            )
        else:
            st.metric("本日損益", "取得中...", None)
    
    # ポジション数（後でMT5PositionProviderから取得）
    with status_cols[2]:
        # TODO: MT5PositionProvider実装後に更新
        st.metric("ポジション", "0/3", None)
    
    # 証拠金率
    with status_cols[3]:
        if account_info:
            margin_level = account_info['margin_level']
            
            # ステータス判定
            if margin_level >= 300:
                status = "安全"
                status_color = "normal"
            elif margin_level >= 200:
                status = "注意"
                status_color = "normal"
            elif margin_level >= 100:
                status = "警告"
                status_color = "inverse"
            else:
                status = "危険"
                status_color = "inverse"
            
            st.metric(
                "証拠金率",
                f"{margin_level:.0f}%",
                status,
                delta_color=status_color
            )
        else:
            st.metric("証拠金率", "取得中...", None)