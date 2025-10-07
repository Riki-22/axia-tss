# src/presentation/ui/streamlit/pages/chart_page.py

import streamlit as st
from components.price_charts.price_chart import PriceChartComponent


def render_chart_page():
    """チャートページのレンダリング"""
    # チャート設定
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        chart_symbol = st.selectbox(
            "通貨ペア",
            ["USDJPY", "EURJPY", "GBPJPY", "EURUSD", "GBPUSD"],
            key="chart_symbol"
        )
    with col2:
        chart_timeframe = st.selectbox(
            "時間足",
            ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            index=5,
            key="chart_timeframe"
        )
    with col3:
        if st.button("🔄 リロード", key="refresh_chart"):
            st.rerun()

    # 注文パネル
    _render_order_panel(chart_symbol)
    
    # チャート表示
    _render_chart(chart_symbol, chart_timeframe)


def _render_order_panel(chart_symbol: str):
    """注文パネルのレンダリング"""
    with st.expander("📃 注文パネル", expanded=True):
        # 注文設定行
        order_cols = st.columns([1, 1, 1, 1, 1])
        
        with order_cols[0]:
            lot_size = st.number_input(
                "ロット",
                min_value=0.01,
                max_value=10.0,
                value=0.10,
                step=0.01,
                format="%.2f",
                key="order_lot"
            )
        
        with order_cols[1]:
            tp_pips = st.number_input(
                "TP (pips)",
                min_value=0,
                max_value=500,
                value=50,
                step=5,
                key="order_tp"
            )
        
        with order_cols[2]:
            sl_pips = st.number_input(
                "SL (pips)",
                min_value=0,
                max_value=500,
                value=25,
                step=5,
                key="order_sl"
            )
        
        with order_cols[3]:
            # リスク計算
            risk = lot_size * sl_pips * 100
            profit = lot_size * tp_pips * 100
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
            <small>リスク: ¥{risk:,.0f}<br>
            利益: ¥{profit:,.0f}</small>
            </div>
            """, unsafe_allow_html=True)
        
        with order_cols[4]:
            # R/R比表示
            rr = tp_pips / sl_pips if sl_pips > 0 else 0
            color = "green" if rr >= 2 else "orange" if rr >= 1 else "red"
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
            <small>R/R比<br>
            <span style='color: {color}; font-size: 18px; font-weight: bold;'>
            {rr:.2f}
            </span></small>
            </div>
            """, unsafe_allow_html=True)
        
        # BUY/SELLボタン
        st.markdown("---")
        buy_col, sell_col = st.columns(2)
        
        with buy_col:
            if st.button(
                f"🔼 BUY {chart_symbol}",
                key="execute_buy",
                width='stretch',
                type="primary"
            ):
                st.success(f"""
                ✅ BUY注文を実行しました
                - {chart_symbol} {lot_size} Lot
                - TP: {tp_pips} pips / SL: {sl_pips} pips
                """)
        
        with sell_col:
            if st.button(
                f"🔽 SELL {chart_symbol}",
                key="execute_sell",
                width='stretch',
                type="secondary"
            ):
                st.error(f"""
                ✅ SELL注文を実行しました
                - {chart_symbol} {lot_size} Lot
                - TP: {tp_pips} pips / SL: {sl_pips} pips
                """)


def _render_chart(symbol: str, timeframe: str):
    """チャートのレンダリング"""
    try:
        fig = PriceChartComponent.render_chart(
            symbol=symbol,
            timeframe=timeframe,
            days=30
        )
        st.plotly_chart(fig, config={'displayModeBar': False})
    except Exception as e:
        st.error(f"チャート表示エラー: {e}")
        st.info("チャートを読み込み中...")

    st.caption("""
    表示要素: ローソク足 | MA(20/75/200) | トレンドチャネル | 
    サポート/レジスタンス | パターン認識（Pinbar/Engulfing/Breakout）
    """)