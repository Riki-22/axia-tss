# src/presentation/ui/streamlit/app.py

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
from services.dynamodb_service import DynamoDBService
from components.price_chart import PriceChartComponent

# サービスのインポート
sys.path.append(str(Path(__file__).parent))

# DynamoDBサービスの初期化
@st.cache_resource
def init_services():
    return DynamoDBService()

db = init_services()

st.set_page_config(
    page_title="AXIA Trading Strategy System", 
    page_icon="📊",
    layout="wide", # 常にwideモードを使用
    initial_sidebar_state="collapsed"  # 初期状態でサイドバーを閉じる
)

# カスタムCSS
st.markdown("""
<style>
    /* ダークテーマ強化 */
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    
    /* サイドバーのグラデーション */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f1e 0%, #1a1a2e 100%);
        width: 320px !important;
    }
    
    /* メトリクスカードのアニメーション */
    [data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    
    [data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
    }
    
    /* ボタンの改善 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    
    /* Kill Switchボタンの特別スタイル */
    button[kind="primary"] {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
    }
    
    /* タブのスタイリング */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 5px;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(102, 126, 234, 0.3);
    }
    
    /* プログレスバーのカスタマイズ */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* ヘッダーのグラデーション */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    
    /* セクションヘッダー */
    .section-header {
        background: rgba(102, 126, 234, 0.1);
        border-left: 4px solid #667eea;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 20px 0 15px 0;
    }
</style>
""", unsafe_allow_html=True)

# === ヘルパー関数（先に定義）===
def show_position_details(position):
    """ポジション詳細表示"""
    st.info(f"{position['チケット']}の詳細を表示")

def render_trading_panel():
    """ポジション管理パネル（広い表示エリア）"""
    
    # === アクティブポジション概要 ===
    st.markdown("### 💹 ポジション管理")
    
    # 概要メトリクス（横幅を活用）
    summary_cols = st.columns(6)
    with summary_cols[0]:
        st.metric("オープン", "3", "ポジション数")
    with summary_cols[1]:
        st.metric("合計損益", "¥125,500", "+5.2%", delta_color="normal")
    with summary_cols[2]:
        st.metric("含み損益", "¥45,200", "+1.8%", delta_color="normal")
    with summary_cols[3]:
        st.metric("実現損益", "¥80,300", "+3.4%", delta_color="normal")
    with summary_cols[4]:
        st.metric("証拠金", "¥285,000", "28.5%使用")
    with summary_cols[5]:
        st.metric("余力", "¥715,000", "71.5%")
    
    st.divider()
    
    # === ポジション一覧（テーブル形式）===
    st.markdown("#### 📍 アクティブポジション")
    
    # データフレームで表示
    import pandas as pd
    
    positions_data = {
        'チケット': ['#1234567', '#1234568', '#1234569'],
        '通貨ペア': ['USDJPY', 'EURUSD', 'GBPJPY'],
        '売買': ['BUY', 'SELL', 'BUY'],
        'ロット': [0.10, 0.20, 0.15],
        'エントリー': [150.250, 1.0850, 185.500],
        '現在値': [150.450, 1.0835, 185.650],
        '損益(円)': ['+¥20,000', '+¥32,000', '+¥15,000'],
        '損益(pips)': ['+20.0', '+15.0', '+15.0'],
        'TP': [151.250, 1.0750, 186.500],
        'SL': [149.750, 1.0900, 185.000]
    }
    
    df = pd.DataFrame(positions_data)
    
    # インタラクティブテーブル
    selected = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        column_config={
            '損益(円)': st.column_config.TextColumn(
                '損益(円)',
                help='現在の損益'
            ),
            'ロット': st.column_config.NumberColumn(
                'ロット',
                format='%.2f'
            ),
            'エントリー': st.column_config.NumberColumn(
                'エントリー',
                format='%.3f'
            ),
            '現在値': st.column_config.NumberColumn(
                '現在値',
                format='%.3f'
            )
        }
    )
    
    # === ポジション操作ボタン（選択したポジションに対して）===
    if selected and selected.selection.rows:
        selected_idx = selected.selection.rows[0]
        selected_position = df.iloc[selected_idx]
        
        st.divider()
        st.markdown(f"#### 🎯 選択中: {selected_position['チケット']} - {selected_position['通貨ペア']}")
        
        action_cols = st.columns(6)
        with action_cols[0]:
            if st.button("📊 詳細表示", use_container_width=True):
                show_position_details(selected_position)
        
        with action_cols[1]:
            if st.button("✏️ TP/SL修正", use_container_width=True):
                show_modify_dialog(selected_position)
        
        with action_cols[2]:
            if st.button("➗ 50%決済", use_container_width=True):
                partial_close_position(selected_position, 0.5)
        
        with action_cols[3]:
            if st.button("🔻 部分決済", use_container_width=True):
                show_partial_close_dialog(selected_position)
        
        with action_cols[4]:
            if st.button("⏸️ ヘッジ", use_container_width=True):
                hedge_position(selected_position)
        
        with action_cols[5]:
            if st.button("❌ 全決済", type="secondary", use_container_width=True):
                close_position(selected_position)
    
    st.divider()
    
    # === 新規注文セクション ===
    with st.expander("📝 新規注文", expanded=False):
        render_new_order_form()
    
    # === 取引履歴 ===
    with st.expander("📜 本日の取引履歴", expanded=False):
        render_trade_history()

# render_trading_panel内で呼び出されている未定義関数を追加

def show_position_details(position):
    """ポジション詳細表示（ダミー実装）"""
    st.info(f"{position['チケット']}の詳細を表示")

def show_modify_dialog(position):
    """TP/SL修正ダイアログ（ダミー実装）"""
    st.info("TP/SL修正機能は実装予定")

def partial_close_position(position, ratio):
    """部分決済（ダミー実装）"""
    st.info(f"{position['チケット']}を{ratio*100}%決済")

def show_partial_close_dialog(position):
    """部分決済ダイアログ（ダミー実装）"""
    st.info("部分決済機能は実装予定")

def hedge_position(position):
    """ヘッジポジション（ダミー実装）"""
    st.info("ヘッジ機能は実装予定")

def close_position(position):
    """ポジション決済（ダミー実装）"""
    st.warning(f"{position['チケット']}を決済")

def render_new_order_form():
    """新規注文フォーム"""
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("通貨ペア", ["USDJPY", "EURUSD", "GBPJPY"])
        st.number_input("ロット", 0.01, 1.0, 0.1, 0.01)
    with col2:
        st.number_input("TP (pips)", 0, 100, 50)
        st.number_input("SL (pips)", 0, 100, 25)
    
    if st.button("注文実行", type="primary", use_container_width=True):
        st.success("注文を実行しました")

def render_trade_history():
    """取引履歴表示"""
    history_data = {
        '時刻': ['14:35', '10:15', '09:45'],
        '通貨': ['GBPJPY', 'AUDUSD', 'EURUSD'],
        '売買': ['BUY', 'SELL', 'BUY'],
        '損益': ['+¥1,250', '-¥850', '+¥2,100']
    }
    import pandas as pd
    st.dataframe(pd.DataFrame(history_data), use_container_width=True)

# Kill Switch状態の取得と表示
kill_switch_status = db.get_kill_switch_status()

# === カラムレイアウト ===
main, right = st.columns([4.0, 1.0])

# =============================
# サイドバー：システム制御
# =============================
with st.sidebar:
    st.markdown("### 📡 システム状態")
    
    if kill_switch_status.get('active'):
        st.error("🚨 **KILL SWITCH ACTIVE** - 全取引停止中")
        st.caption(f"最終更新: {kill_switch_status.get('last_updated', 'N/A')}")
    else:
        st.success("✅ システム正常稼働中")

    conn_test = db.test_connection()
    if conn_test['status'] == 'SUCCESS':
        st.success(f"✅ DB接続: {conn_test['table']}")
    else:
        st.error("❌ DB接続エラー")
        st.caption(conn_test.get('error', 'Unknown error'))
    
    if st.button("🔄 更新", key="refresh"):
        st.rerun()

    st.caption(f"最終確認: {datetime.now().strftime('%H:%M:%S')}")

    st.markdown("---")
    st.markdown("### ⚙️ Control Panel")
    
    # 取引パラメータ
    with st.expander("📊 取引設定", expanded=True):
        st.selectbox("通貨ペア", ["USDJPY", "EURJPY", "GBPJPY", "EURUSD", "GBPUSD"])
        st.selectbox("時間足", ["M1", "M5", "M15", "M30", "H1", "H4", "D1"], index=5)
        st.selectbox("期間", ["1週間", "1ヶ月", "3ヶ月", "6ヶ月", "1年"], index=2)
    
    # 資金管理
    with st.expander("💰 資金管理", expanded=True):
        st.slider("1取引リスク(%)", 0.5, 5.0, 2.0, 0.5)
        st.number_input("最大同時ポジション", 1, 10, 3)
        st.number_input("日次最大損失(%)", 1, 20, 5)
        st.number_input("最大DD許容値(%)", 5, 30, 15)
        st.selectbox("サイジング", ["固定ロット", "%リスク", "ケリー基準"], index=1)
    
    # アラート設定
    with st.expander("🔔 アラート設定"):
        st.checkbox("ドローダウン警告", value=True)
        st.checkbox("証拠金維持率", value=True)
        st.checkbox("ポジションオープン通知", value=True)
        st.checkbox("TP/SL到達通知", value=True)
    
    # Kill Switch
    st.markdown("---")
    with st.container():
        st.markdown("#### 🚨 緊急停止")
        
        current_status = kill_switch_status.get('status', 'OFF')
        if current_status == 'ON':
            if st.button("🔓 **Kill Switch 解除**", type="secondary", use_container_width=True):
                result = db.set_kill_switch('OFF')
                if result['success']:
                    st.success("Kill Switch を解除しました")
                    st.rerun()
                else:
                    st.error(f"エラー: {result.get('error')}")
        else:
            if st.button("🛑 **KILL SWITCH 発動**", type="primary", use_container_width=True):
                result = db.set_kill_switch('ON')
                if result['success']:
                    st.warning("Kill Switch を発動しました")
                    st.rerun()
                else:
                    st.error(f"エラー: {result.get('error')}")
        st.checkbox("全ポジション決済", key="ks1")
        st.checkbox("全注文キャンセル", key="ks2")
        st.checkbox("新規取引停止", key="ks3")

# =============================
# 中央：メイン情報表示
# =============================
with main:
    st.markdown("## 📊 AXIA Trading Strategy System")
    
    # システムステータス
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("現在価格", "150.250", "+0.05")
    with status_cols[1]:
        st.metric("本日損益", "+2.45%", "+¥12,500")
    with status_cols[2]:
        st.metric("ポジション", "2/3", None)
    with status_cols[3]:
        st.metric("証拠金率", "285%", "安全")
    
    # メインタブ
    chart_tab, position_tab, signal_tab, analysis_tab = st.tabs([
        "📈 チャート", 
        "💼 ポジション管理",
        "⚡ シグナル", 
        "🎯 分析"
    ])
    
    with chart_tab:
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
            if st.button("🔄 更新", key="refresh_chart"):
                st.rerun()
        
        # チャート表示
        try:
            fig = PriceChartComponent.render_chart(
                symbol=chart_symbol,
                timeframe=chart_timeframe,
                days=30
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"チャート表示エラー: {e}")
            st.info("チャートを読み込み中...")

            st.caption("""
            表示要素: ローソク足 | MA(20/75/200) | トレンドチャネル | 
            サポート/レジスタンス | パターン認識（Pinbar/Engulfing/Breakout）
            """)
    
    with position_tab:
        render_trading_panel() 

    with signal_tab:
        # シグナル分析
        st.markdown("#### シグナル統合")
        sig1, sig2, sig3 = st.columns(3)
        
        with sig1:
            st.markdown("**📈 トレンド系**")
            st.success("MACD: BUY")
            st.success("MA Cross: BUY")
            st.info("Breakout: 監視中")
        
        with sig2:
            st.markdown("**📊 オシレーター**")
            st.warning("RSI: 中立(45)")
            st.success("Stochastic: BUY")
            st.error("RCI: SELL")
        
        with sig3:
            st.markdown("**💨 ボラティリティ**")
            st.success("BB: 下部タッチ")
            st.info("ATR: 0.0045")
            st.success("Squeeze: 拡大")
        
        # 統合分析
        st.markdown("---")
        st.markdown("#### ⚡ 統合シグナル分析")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**推奨アクション**")
            st.success("### BUY")
            st.progress(75, "シグナル強度: 75%")
        with col2:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("トレンド", "+3/3", "✓")
            with c2:
                st.metric("オシレーター", "+2/3", "✓")
            with c3:
                st.metric("ボラティリティ", "+2/3", "✓")
    
    with analysis_tab:
        # ベイジアン分析
        st.markdown("#### 🧠 ベイジアン確率分析")
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.metric("成功確率", "72.3%", "+17.3%")
        with b2:
            st.metric("事前確率", "55.0%", None)
        with b3:
            st.metric("尤度", "0.85", None)
        with b4:
            st.metric("推奨ロット", "0.73", None)
        
        # 市場レジーム
        st.markdown("#### 🌡️ 市場レジーム分析")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.info("**レジーム**: 上昇トレンド")
            st.progress(78, "信頼度: 78%")
        with r2:
            st.metric("トレンド強度", "強", "↑")
        with r3:
            st.metric("ボラティリティ", "中", "→")
        
        # パフォーマンス
        st.markdown("#### 📊 パフォーマンス指標")
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            st.metric("Sharpe Ratio", "1.85", "+0.12")
        with p2:
            st.metric("勝率", "68.5%", "→")
        with p3:
            st.metric("PF", "2.1", "+0.15")
        with p4:
            st.metric("最大DD", "-8.2%", "-1.2%")

# =============================
# 右カラム：取引実行・管理
# =============================
with right:
    st.markdown("### 💹 Trading Panel")
    
    tab_pos, tab_ord, tab_hist = st.tabs(["ポジション", "注文", "履歴"])
    
    with tab_pos:
        st.markdown("#### 📍 アクティブポジション")
        
        # ポジション概要
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("合計", "2", None, label_visibility="visible")
        with c2:
            st.metric("損益", "+¥12,500", None)
        with c3:
            st.metric("証拠金", "¥85,000", None)
        
        # ポジション1
        with st.container():
            st.markdown("---")
            st.markdown("**#1234567** USDJPY **BUY** 0.1 Lot")
            col1, col2 = st.columns(2)
            with col1:
                st.caption("Entry: 150.250")
                st.caption("Current: 150.450")
            with col2:
                st.caption("**+20 pips**")
                st.caption("**+¥2,000**")
            
            b1, b2, b3 = st.columns(3)
            with b1:
                st.button("50%決済", key="p1_1")
            with b2:
                st.button("TP/SL", key="p1_2")
            with b3:
                st.button("全決済", key="p1_3")
        
        # ポジション2
        with st.container():
            st.markdown("---")
            st.markdown("**#1234568** EURUSD **SELL** 0.2 Lot")
            col1, col2 = st.columns(2)
            with col1:
                st.caption("Entry: 1.0850")
                st.caption("Current: 1.0835")
            with col2:
                st.caption("**+15 pips**")
                st.caption("**+¥3,200**")
            
            b1, b2, b3 = st.columns(3)
            with b1:
                st.button("50%決済", key="p2_1")
            with b2:
                st.button("TP/SL", key="p2_2")
            with b3:
                st.button("全決済", key="p2_3")
    
    with tab_ord:
        st.markdown("#### 📝 新規注文")
        st.selectbox("通貨ペア", ["USDJPY", "EURUSD", "GBPJPY"], key="ord_sym")
        st.radio("注文タイプ", ["成行", "指値", "逆指値"], key="ord_type")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("BUY", type="primary", use_container_width=True):
                st.success("BUY選択")
        with col2:
            if st.button("SELL", type="secondary", use_container_width=True):
                st.error("SELL選択")
        
        st.number_input("ロット", 0.01, 10.0, 0.1, 0.01, key="ord_lot")
        st.number_input("TP (pips)", value=50, key="ord_tp")
        st.number_input("SL (pips)", value=25, key="ord_sl")
        
        st.button("**注文実行**", type="primary", use_container_width=True, key="exec")
    
    with tab_hist:
        st.markdown("#### 📜 取引履歴")
        
        # 履歴1
        with st.container():
            st.markdown("**GBPJPY BUY** 0.1 Lot")
            st.caption("2025-01-20 14:35 → 16:22")
            st.success("+12 pips (+¥1,250)")
        
        st.markdown("---")
        
        # 履歴2
        with st.container():
            st.markdown("**AUDUSD SELL** 0.15 Lot")
            st.caption("2025-01-20 10:15 → 11:30")
            st.error("-8 pips (-¥850)")