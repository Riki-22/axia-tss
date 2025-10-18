# src/presentation/ui/streamlit/pages/trading_page.py

import streamlit as st
import logging
from components.trading_charts.price_chart import PriceChartComponent
from components.trading_charts.chart_data_source import get_chart_data_source
from src.infrastructure.di.container import DIContainer

logger = logging.getLogger(__name__)
container = DIContainer()


def render_trading_page():
    """チャートページ"""
    
    # データソース取得
    data_source = get_chart_data_source()
    
    # 注文パブリッシャー取得
    try:
        order_publisher = container.get_sqs_order_publisher()
    except Exception as e:
        logger.error(f"Failed to initialize order publisher: {e}")
        order_publisher = None
        st.error("⚠️ 注文機能が利用できません")
    
    # チャート設定
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
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
            index=4,  # H1
            key="chart_timeframe"
        )
    
    with col3:
        days = st.number_input("日数", 1, 90, 30, key="chart_days")
    
    with col4:
        # 🔄リロードボタン（force_refresh）
        if st.button("🔄 リロード", key="refresh_chart", help="MT5から最新データを取得"):
            with st.spinner("最新データ取得中..."):
                df, metadata = data_source.force_refresh(
                    chart_symbol, chart_timeframe, days
                )
            if df is not None:
                st.success("✅ 最新データを取得しました")
                st.rerun()  # 画面を再描画
            else:
                st.error("❌ データ取得に失敗しました")
                if 'error' in metadata:
                    st.caption(f"エラー: {metadata['error']}")
    
    # 注文パネル
    _render_order_panel(chart_symbol, order_publisher)
    
    # データ取得
    with st.spinner('Loading chart...'):
        df, metadata = data_source.get_ohlcv_data(
            chart_symbol, chart_timeframe, days
        )
    
    if df is not None:
        # データ鮮度情報表示
        _render_data_freshness(metadata)
        
        # データソース情報（サイドバー）
        _render_data_info_sidebar(chart_symbol, chart_timeframe, metadata)
        
        # チャート描画
        _render_chart_display(df, chart_symbol, chart_timeframe, days)
    else:
        st.error("データ取得に失敗しました")
        if 'error' in metadata:
            with st.expander("エラー詳細"):
                st.code(metadata['error'])


def _render_order_panel(chart_symbol: str, order_publisher):
    """
    注文パネルのレンダリング（完全実装版）
    
    機能:
    - ロット数、TP/SL設定
    - リスク・利益計算
    - R/R比表示
    - BUY/SELL注文送信
    """
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
                key="order_lot",
                help="取引ロット数（0.01〜10.0）"
            )
        
        with order_cols[1]:
            tp_pips = st.number_input(
                "TP (pips)",
                min_value=0,
                max_value=500,
                value=50,
                step=5,
                key="order_tp",
                help="利確までのpips数"
            )
        
        with order_cols[2]:
            sl_pips = st.number_input(
                "SL (pips)",
                min_value=0,
                max_value=500,
                value=25,
                step=5,
                key="order_sl",
                help="損切までのpips数"
            )
        
        with order_cols[3]:
            # リスク計算（1pips = ¥100/ロット想定）
            risk = lot_size * sl_pips * 100
            profit = lot_size * tp_pips * 100
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
            <small style='color: #888;'>想定リスク</small><br>
            <span style='color: #ff4b4b; font-weight: bold;'>¥{risk:,.0f}</span><br>
            <small style='color: #888;'>想定利益</small><br>
            <span style='color: #21c354; font-weight: bold;'>¥{profit:,.0f}</span>
            </div>
            """, unsafe_allow_html=True)
        
        with order_cols[4]:
            # R/R比表示
            rr = tp_pips / sl_pips if sl_pips > 0 else 0
            
            if rr >= 2:
                color = "#21c354"  # 緑
                rating = "優秀"
            elif rr >= 1.5:
                color = "#ffa500"  # オレンジ
                rating = "良好"
            elif rr >= 1:
                color = "#ff8c00"  # ダークオレンジ
                rating = "普通"
            else:
                color = "#ff4b4b"  # 赤
                rating = "要改善"
            
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
            <small style='color: #888;'>R/R比</small><br>
            <span style='color: {color}; font-size: 24px; font-weight: bold;'>
            {rr:.2f}
            </span><br>
            <small style='color: {color};'>{rating}</small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 注文実行ボタン
        buy_col, sell_col = st.columns(2)
        
        with buy_col:
            if st.button(
                f"🔼 BUY {chart_symbol}",
                key="execute_buy",
                type="primary",
                use_container_width=True
            ):
                _execute_order(
                    symbol=chart_symbol,
                    action="BUY",
                    lot_size=lot_size,
                    tp_pips=tp_pips,
                    sl_pips=sl_pips,
                    order_publisher=order_publisher
                )
        
        with sell_col:
            if st.button(
                f"🔽 SELL {chart_symbol}",
                key="execute_sell",
                type="secondary",
                use_container_width=True
            ):
                _execute_order(
                    symbol=chart_symbol,
                    action="SELL",
                    lot_size=lot_size,
                    tp_pips=tp_pips,
                    sl_pips=sl_pips,
                    order_publisher=order_publisher
                )


def _execute_order(
    symbol: str,
    action: str,
    lot_size: float,
    tp_pips: int,
    sl_pips: int,
    order_publisher
):
    """
    注文実行（SQS送信）
    
    処理フロー:
    1. 現在価格取得（ダミー実装）
    2. TP/SL価格計算
    3. 注文データ作成
    4. SQS送信
    5. 結果表示
    
    Args:
        symbol: 通貨ペア
        action: 'BUY' or 'SELL'
        lot_size: ロット数
        tp_pips: 利確pips
        sl_pips: 損切pips
        order_publisher: SQSOrderPublisher
    """
    try:
        # 現在価格取得（暫定実装：固定値）
        # TODO: OhlcvDataProviderから現在価格を取得
        current_prices = {
            'USDJPY': 150.0,
            'EURJPY': 165.0,
            'GBPJPY': 190.0,
            'EURUSD': 1.10,
            'GBPUSD': 1.27
        }
        current_price = current_prices.get(symbol, 150.0)
        
        # pip値の計算
        # JPYペア: 0.01
        # その他: 0.0001
        pip_value = 0.01 if 'JPY' in symbol else 0.0001
        
        # TP/SL価格計算
        if action == "BUY":
            tp_price = current_price + (tp_pips * pip_value)
            sl_price = current_price - (sl_pips * pip_value)
        else:  # SELL
            tp_price = current_price - (tp_pips * pip_value)
            sl_price = current_price + (sl_pips * pip_value)
        
        # 注文データ作成
        order_data = {
            'symbol': symbol,
            'order_action': action,
            'order_type': 'MARKET',
            'lot_size': lot_size,
            'tp_price': round(tp_price, 5),
            'sl_price': round(sl_price, 5),
            'comment': 'Streamlit_Manual_Order'
        }
        
        logger.info(f"Executing order: {order_data}")
        
        # SQS送信
        with st.spinner('注文送信中...'):
            success, message = order_publisher.send_order(order_data)
        
        if success:
            # 成功メッセージ
            rr = tp_pips / sl_pips if sl_pips > 0 else 0
            risk_amount = lot_size * sl_pips * 100
            profit_amount = lot_size * tp_pips * 100
            
            # MOCKモード判定
            is_mock = message.startswith('mock-')
            mode_label = "🧪 **MOCK MODE**" if is_mock else "✅"
            
            st.success(f"""
            {mode_label} **{action}注文を送信しました**
            
            **注文内容**:
            - 通貨ペア: `{symbol}`
            - ロット: `{lot_size}`
            - エントリー: `{current_price:.5f}` (参考)
            - TP: `{tp_price:.5f}` ({tp_pips} pips)
            - SL: `{sl_price:.5f}` ({sl_pips} pips)
            - R/R比: `{rr:.2f}`
            
            **リスク・リターン**:
            - 想定損失: ¥{risk_amount:,.0f}
            - 想定利益: ¥{profit_amount:,.0f}
            
            **処理状況**:
            - MessageID: `{message[:30]}...`
            {('- ⚠️ AWS未接続のため実際の注文は実行されません' if is_mock else '- order_managerで処理中...')}
            
            {('💡 AWS認証情報を設定すると実際のSQS送信が可能になります' if is_mock else '💡 **ポジションページ**で実行結果を確認できます')}
            """)
            
            logger.info(
                f"Order sent successfully: {symbol} {action} {lot_size} lot, "
                f"MessageID={message}"
            )
            
        else:
            # 失敗メッセージ
            st.error(f"""
            ❌ **注文送信に失敗しました**
            
            **エラー**: {message}
            
            以下をご確認ください:
            - Kill Switchが無効になっているか
            - SQSキューが正常に動作しているか
            - ネットワーク接続が安定しているか
            """)
            
            logger.error(f"Order send failed: {message}")
            
    except Exception as e:
        # 例外発生時
        st.error(f"""
        ❌ **注文処理エラー**
        
        {str(e)}
        
        システム管理者に連絡してください。
        """)
        logger.error(f"Order execution error: {e}", exc_info=True)


def _render_chart_display(df, symbol, timeframe, days):
    """
    チャート描画
    
    Args:
        df: OHLCVデータ（既に取得済み）
        symbol: 通貨ペア
        timeframe: 時間足
        days: 表示日数
    """
    try:
        fig = PriceChartComponent.render_chart(
            symbol=symbol,
            timeframe=timeframe,
            days=days
        )
        st.plotly_chart(
            fig,
            config={'displayModeBar': False},
            use_container_width=True
        )
    except Exception as e:
        st.error(f"チャート表示エラー: {e}")
        logger.error(f"Chart render error: {e}", exc_info=True)


def _render_data_freshness(metadata: dict):
    """
    データ鮮度情報の表示
    
    Args:
        metadata: データメタデータ
            - data_age: データエイジ（秒）
            - fresh: 新鮮フラグ
            - source: データソース
    """
    if 'data_age' in metadata:
        age_seconds = metadata['data_age']
        
        # データエイジに応じた表示
        if age_seconds < 300:  # 5分以内
            st.success(f"✅ 最新データ（{int(age_seconds)}秒前）")
        elif age_seconds < 3600:  # 1時間以内
            minutes = int(age_seconds / 60)
            st.info(f"ℹ️ {minutes}分前のデータ")
        elif age_seconds < 86400:  # 24時間以内
            hours = int(age_seconds / 3600)
            st.warning(
                f"⚠️ {hours}時間前のデータ "
                f"（🔄ボタンで更新推奨）"
            )
        else:  # 24時間以上
            days = int(age_seconds / 86400)
            st.error(
                f"❌ {days}日前のデータ "
                f"（🔄ボタンで更新してください）"
            )
    elif metadata.get('fresh'):
        st.success("✅ 最新データ")
    elif metadata.get('source'):
        # 鮮度情報なしだが取得成功
        source = metadata['source']
        st.info(f"ℹ️ {source.upper()}から取得")


def _render_data_info_sidebar(symbol: str, timeframe: str, metadata: dict):
    """
    データソース情報をサイドバーに表示
    
    Args:
        symbol: 通貨ペア
        timeframe: 時間足
        metadata: データメタデータ
    """
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📡 Data Info")
        
        # データソース表示
        source = metadata.get('source', 'unknown')
        emoji_map = {
            'redis': '⚡',
            's3': '📦',
            'mt5': '🔌',
            'yfinance': '🌐'
        }
        emoji = emoji_map.get(source, '❓')
        
        st.info(f"{emoji} **{source.upper()}**")
        
        # メトリクス表示
        col1, col2 = st.columns(2)
        
        with col1:
            if 'row_count' in metadata:
                st.metric("Rows", f"{metadata['row_count']:,}")
            elif 'rows' in metadata:
                st.metric("Rows", f"{metadata['rows']:,}")
        
        with col2:
            if 'response_time' in metadata:
                st.metric("Time", f"{metadata['response_time']:.2f}s")
        
        # データエイジ表示
        if 'data_age' in metadata:
            age = int(metadata['data_age'])
            
            if age < 60:
                age_str = f"{age}秒前"
            elif age < 3600:
                age_str = f"{age//60}分前"
            elif age < 86400:
                age_str = f"{age//3600}時間前"
            else:
                age_str = f"{age//86400}日前"
            
            st.caption(f"📅 Age: {age_str}")
        
        # キャッシュヒット表示
        if 'cache_hit' in metadata:
            if metadata['cache_hit']:
                st.caption("✅ Cache Hit")
            else:
                st.caption("🔄 Fresh Fetch")
        
        # 鮮度表示
        if 'fresh' in metadata:
            if metadata['fresh']:
                st.caption("🌟 Fresh Data")
            else:
                st.caption("⚠️ Stale Data")