# src/presentation/ui/streamlit/pages/position_page.py

import streamlit as st
import pandas as pd
from typing import Dict, Any


def render_position_page():
    """ポジション管理ページのレンダリング"""
    _render_position_summary()
    st.divider()
    _render_active_positions()
    st.divider()
    _render_trade_history()


def _render_position_summary():
    """ポジション概要の表示"""
    st.markdown("#### 💹 ポジション管理")
    
    # 概要メトリクス
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


def _render_active_positions():
    """アクティブポジションの表示"""
    st.markdown("#### 📍 アクティブポジション")
    
    # ダミーデータ
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
        width='stretch',
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
    
    # ポジション操作
    if selected and selected.selection.rows:
        _render_position_actions(df, selected.selection.rows[0])


def _render_position_actions(df: pd.DataFrame, selected_idx: int):
    """選択されたポジションに対するアクション"""
    selected_position = df.iloc[selected_idx]
    
    st.divider()
    st.markdown(f"#### 🎯 選択中: {selected_position['チケット']} - {selected_position['通貨ペア']}")
    
    action_cols = st.columns(6)
    with action_cols[0]:
        if st.button("📊 詳細表示", width='stretch'):
            _show_position_details(selected_position)
    
    with action_cols[1]:
        if st.button("✏️ TP/SL修正", width='stretch'):
            _show_modify_dialog(selected_position)
    
    with action_cols[2]:
        if st.button("➗ 50%決済", width='stretch'):
            _partial_close_position(selected_position, 0.5)
    
    with action_cols[3]:
        if st.button("🔻 部分決済", width='stretch'):
            _show_partial_close_dialog(selected_position)
    
    with action_cols[4]:
        if st.button("⏸️ ヘッジ", width='stretch'):
            _hedge_position(selected_position)
    
    with action_cols[5]:
        if st.button("❌ 全決済", type="secondary", width='stretch'):
            _close_position(selected_position)


def _render_trade_history():
    """取引履歴の表示"""
    st.markdown("#### 📜 本日の取引履歴")
    
    history_data = {
        '時刻': ['14:35', '10:15', '09:45'],
        '通貨': ['GBPJPY', 'AUDUSD', 'EURUSD'],
        '売買': ['BUY', 'SELL', 'BUY'],
        '損益': ['+¥1,250', '-¥850', '+¥2,100']
    }
    
    st.dataframe(pd.DataFrame(history_data), width='stretch')


# ヘルパー関数（ダミー実装）
def _show_position_details(position):
    st.info(f"{position['チケット']}の詳細を表示")

def _show_modify_dialog(position):
    st.info("TP/SL修正機能は実装予定")

def _partial_close_position(position, ratio):
    st.info(f"{position['チケット']}を{ratio*100}%決済")

def _show_partial_close_dialog(position):
    st.info("部分決済機能は実装予定")

def _hedge_position(position):
    st.info("ヘッジ機能は実装予定")

def _close_position(position):
    st.warning(f"{position['チケット']}を決済")