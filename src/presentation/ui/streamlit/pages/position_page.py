# src/presentation/ui/streamlit/pages/position_page.py

import streamlit as st
import pandas as pd
import logging
from typing import Dict, List, Optional
from src.infrastructure.di.container import container

logger = logging.getLogger(__name__)


def render_position_page():
    """ポジション管理ページのレンダリング"""
    st.markdown("#### 💹 ポジション管理")
    
    # セッション状態初期化
    if 'selected_position_ticket' not in st.session_state:
        st.session_state.selected_position_ticket = None
    if 'position_action_result' not in st.session_state:
        st.session_state.position_action_result = None
    
    # MT5PositionProviderとMT5AccountProviderを取得
    try:
        position_provider = container.get_mt5_position_provider()
        account_provider = container.get_mt5_account_provider()
    except Exception as e:
        st.error("⚠️ MT5サービスの初期化に失敗しました")
        logger.error(f"Failed to initialize MT5 services: {e}")
        return
    
    # アクション結果の表示
    if st.session_state.position_action_result:
        if st.session_state.position_action_result['success']:
            st.success(st.session_state.position_action_result['message'])
        else:
            st.error(st.session_state.position_action_result['message'])
        st.session_state.position_action_result = None
    
    # ページ構成
    _render_position_summary(position_provider, account_provider)
    st.divider()
    _render_active_positions(position_provider)


def _render_position_summary(position_provider, account_provider):
    """ポジション概要の表示"""
    
    # データ取得
    positions = position_provider.get_all_positions()
    account_info = account_provider.get_account_info()
    today_pl = account_provider.calculate_today_pl()
    
    # 統計計算
    total_unrealized_pnl = sum(pos['profit'] for pos in positions)
    realized_pnl = today_pl['amount'] - total_unrealized_pnl if today_pl else 0.0
    
    # 概要メトリクス（6列）
    summary_cols = st.columns(6)
    
    with summary_cols[0]:
        st.metric("オープン", f"{len(positions)}", "ポジション")
    
    with summary_cols[1]:
        if today_pl:
            amount = today_pl['amount']
            percentage = today_pl['percentage']
            delta_color = "normal" if amount >= 0 else "inverse"
            st.metric(
                "本日損益",
                f"¥{amount:+,.0f}",
                f"{percentage:+.2f}%",
                delta_color=delta_color
            )
        else:
            st.metric("本日損益", "取得中...", None)
    
    with summary_cols[2]:
        delta_color = "normal" if total_unrealized_pnl >= 0 else "inverse"
        st.metric(
            "含み損益",
            f"¥{total_unrealized_pnl:+,.0f}",
            f"{len(positions)}ポジション",
            delta_color=delta_color
        )
    
    with summary_cols[3]:
        delta_color = "normal" if realized_pnl >= 0 else "inverse"
        st.metric(
            "実現損益",
            f"¥{realized_pnl:+,.0f}",
            "本日分",
            delta_color=delta_color
        )
    
    with summary_cols[4]:
        if account_info:
            margin = account_info['margin']
            equity = account_info['equity']
            margin_pct = (margin / equity * 100) if equity > 0 else 0
            st.metric(
                "使用証拠金",
                f"¥{margin:,.0f}",
                f"{margin_pct:.1f}%使用"
            )
        else:
            st.metric("使用証拠金", "取得中...", None)
    
    with summary_cols[5]:
        if account_info:
            free_margin = account_info['free_margin']
            equity = account_info['equity']
            free_pct = (free_margin / equity * 100) if equity > 0 else 0
            st.metric(
                "余力",
                f"¥{free_margin:,.0f}",
                f"{free_pct:.1f}%"
            )
        else:
            st.metric("余力", "取得中...", None)


def _render_active_positions(position_provider):
    """アクティブポジションの表示"""
    st.markdown("#### 📍 アクティブポジション")
    
    # リアルタイムポジション取得
    try:
        positions = position_provider.get_all_positions()
    except Exception as e:
        st.error("⚠️ ポジション情報の取得に失敗しました")
        logger.error(f"Failed to get positions: {e}")
        return
    
    if not positions:
        st.info("📭 現在オープンポジションはありません")
        return
    
    # DataFrame作成（MT5データから）
    df_data = []
    for pos in positions:
        df_data.append({
            'チケット': f"#{pos['ticket']}",
            '通貨ペア': pos['symbol'],
            '売買': pos['type'],
            'ロット': pos['volume'],
            'エントリー': pos['price_open'],
            '現在値': pos['price_current'],
            '損益(円)': f"¥{pos['profit']:+,.0f}",
            '損益(pips)': f"{pos['profit_pips']:+.1f}",
            'TP': pos['tp'] if pos['tp'] > 0 else 'なし',
            'SL': pos['sl'] if pos['sl'] > 0 else 'なし'
        })
    
    df = pd.DataFrame(df_data)
    
    # インタラクティブテーブル
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="position_table",
        column_config={
            'チケット': st.column_config.TextColumn('チケット', width="small"),
            '通貨ペア': st.column_config.TextColumn('通貨ペア', width="small"),
            '売買': st.column_config.TextColumn('売買', width="small"),
            'ロット': st.column_config.NumberColumn('ロット', format='%.2f', width="small"),
            'エントリー': st.column_config.NumberColumn('エントリー', format='%.5f', width="medium"),
            '現在値': st.column_config.NumberColumn('現在値', format='%.5f', width="medium"),
            '損益(円)': st.column_config.TextColumn('損益(円)', width="medium"),
            '損益(pips)': st.column_config.TextColumn('損益(pips)', width="small"),
            'TP': st.column_config.TextColumn('TP', width="medium"),
            'SL': st.column_config.TextColumn('SL', width="medium")
        }
    )
    
    # ポジション操作
    if event.selection.rows:
        selected_idx = event.selection.rows[0]
        selected_position_data = positions[selected_idx]  # 元のMT5データを使用
        
        # セッション状態に選択ポジション保存
        st.session_state.selected_position_ticket = selected_position_data['ticket']
        
        _render_position_actions(selected_position_data, position_provider)
    elif st.session_state.selected_position_ticket:
        # 前回選択されたポジションを維持
        selected_pos = next(
            (pos for pos in positions if pos['ticket'] == st.session_state.selected_position_ticket),
            None
        )
        if selected_pos:
            _render_position_actions(selected_pos, position_provider)


def _render_position_actions(position_data: Dict, position_provider):
    """選択されたポジションに対するアクション"""
    st.divider()
    st.markdown(
        f"#### 🎯 選択中: #{position_data['ticket']} - {position_data['symbol']}"
    )
    
    # ポジション詳細表示
    with st.expander("📊 ポジション詳細", expanded=False):
        detail_cols = st.columns(2)
        
        with detail_cols[0]:
            st.markdown(f"""
            **基本情報**:
            - チケット: `#{position_data['ticket']}`
            - 通貨ペア: `{position_data['symbol']}`
            - 売買: `{position_data['type']}`
            - ロット: `{position_data['volume']}`
            - エントリー価格: `{position_data['price_open']:.5f}`
            - 現在価格: `{position_data['price_current']:.5f}`
            """)
        
        with detail_cols[1]:
            # TP/SL表示用の値を事前計算
            tp_display = f"{position_data['tp']:.5f}" if position_data['tp'] > 0 else 'なし'
            sl_display = f"{position_data['sl']:.5f}" if position_data['sl'] > 0 else 'なし'
            
            st.markdown(f"""
            **損益情報**:
            - 損益（円）: `¥{position_data['profit']:+,.0f}`
            - 損益（pips）: `{position_data['profit_pips']:+.1f} pips`
            - スワップ: `¥{position_data['swap']:+,.2f}`
            - TP: `{tp_display}`
            - SL: `{sl_display}`
            """)
        
        st.caption(f"オープン時刻: {position_data['time'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        st.caption(f"Magic Number: {position_data['magic']}")
        st.caption(f"コメント: {position_data['comment']}")
    
    # 操作ボタン
    action_cols = st.columns(6)
    
    with action_cols[0]:
        if st.button("🔄 更新", key=f"refresh_{position_data['ticket']}"):
            # 選択状態を維持したまま更新
            st.rerun()
    
    with action_cols[1]:
        if st.button("50%決済", key=f"partial50_{position_data['ticket']}"):
            # 即座実行
            _partial_close_position(
                position_data['ticket'],
                position_data['volume'] * 0.5,
                position_provider
            )
    
    with action_cols[2]:
        # 部分決済ダイアログトグル
        dialog_key = f"show_partial_dialog_{position_data['ticket']}"
        if dialog_key not in st.session_state:
            st.session_state[dialog_key] = False
        
        if st.button("部分決済", key=f"partial_{position_data['ticket']}"):
            st.session_state[dialog_key] = not st.session_state[dialog_key]
            st.rerun()
    
    with action_cols[3]:
        # Phase 2実装予定
        st.button("✏️ TP変更", disabled=True, key=f"tp_{position_data['ticket']}")
    
    with action_cols[4]:
        # Phase 2実装予定  
        st.button("✏️ SL変更", disabled=True, key=f"sl_{position_data['ticket']}")
    
    with action_cols[5]:
        if st.button("❌ 全決済", type="primary", key=f"close_{position_data['ticket']}"):
            _close_position(position_data['ticket'], position_provider)
    
    # 部分決済ダイアログ表示
    dialog_key = f"show_partial_dialog_{position_data['ticket']}"
    if st.session_state.get(dialog_key, False):
        _show_partial_close_dialog(position_data, position_provider)


def _partial_close_position(ticket: int, volume: float, position_provider):
    """部分決済実行（SQS統一アーキテクチャ）"""
    try:
        # ポジション情報取得（SQSメッセージ作成用）
        position_info = position_provider.get_position_by_ticket(ticket)
        if not position_info:
            st.session_state.position_action_result = {
                'success': False,
                'message': f"❌ ポジション #{ticket} が見つかりません"
            }
            st.rerun()
            return
        
        # CLOSE注文メッセージ作成（部分決済）
        close_order_data = {
            'symbol': position_info['symbol'],
            'order_action': 'CLOSE',
            'order_type': 'MARKET', 
            'lot_size': volume,  # 部分決済ロット数
            'mt5_ticket': ticket,
            'tp_price': 0.0,  # CLOSE注文では不要
            'sl_price': 0.0,  # CLOSE注文では不要
            'comment': f'Streamlit_Partial_Close_{volume}'
        }
        
        # SQS送信
        order_publisher = container.get_sqs_order_publisher()
        success, message_id = order_publisher.send_order(close_order_data)
        
        if success:
            st.session_state.position_action_result = {
                'success': True,
                'message': f"✅ ポジション #{ticket} の {volume} ロット決済注文を送信しました"
            }
            logger.info(f"Partial close order sent via SQS: {ticket}, volume={volume}, MessageID={message_id}")
        else:
            st.session_state.position_action_result = {
                'success': False,
                'message': f"❌ 部分決済注文送信に失敗しました: {message_id}"
            }
            logger.error(f"Partial close SQS send failed: {ticket}, error={message_id}")
        
        st.rerun()
        
    except Exception as e:
        st.session_state.position_action_result = {
            'success': False,
            'message': f"❌ 部分決済エラー: {str(e)}"
        }
        logger.error(f"Exception during partial close: {e}", exc_info=True)
        st.rerun()


def _show_partial_close_dialog(position_data: Dict, position_provider):
    """部分決済ダイアログ"""
    max_volume = position_data['volume']
    
    with st.form(key=f"partial_close_form_{position_data['ticket']}"):
        st.markdown(f"**ポジション #{position_data['ticket']} 部分決済**")
        
        volume = st.number_input(
            "決済ロット数",
            min_value=0.01,
            max_value=max_volume,
            value=max_volume * 0.5,
            step=0.01,
            format="%.2f",
            help=f"最大: {max_volume} ロット"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💰 部分決済実行", type="primary"):
                # フォーム外の関数を使用
                st.session_state.partial_close_ticket = position_data['ticket']
                st.session_state.partial_close_volume = volume
                st.rerun()
        
        with col2:
            if st.form_submit_button("❌ キャンセル"):
                st.rerun()
    
    # フォーム外で実際の決済処理
    if hasattr(st.session_state, 'partial_close_ticket') and st.session_state.partial_close_ticket:
        ticket = st.session_state.partial_close_ticket
        volume = st.session_state.partial_close_volume
        
        # 状態クリア
        st.session_state.partial_close_ticket = None
        st.session_state.partial_close_volume = None
        
        # 決済実行
        _partial_close_position(ticket, volume, position_provider)


def _close_position(ticket: int, position_provider):
    """全決済実行（SQS統一アーキテクチャ）"""
    try:
        # ポジション情報取得（SQSメッセージ作成用）
        position_info = position_provider.get_position_by_ticket(ticket)
        if not position_info:
            st.session_state.position_action_result = {
                'success': False,
                'message': f"❌ ポジション #{ticket} が見つかりません"
            }
            st.rerun()
            return
        
        # CLOSE注文メッセージ作成
        close_order_data = {
            'symbol': position_info['symbol'],
            'order_action': 'CLOSE',
            'order_type': 'MARKET',
            'lot_size': position_info['volume'],  # 全決済
            'mt5_ticket': ticket,
            'tp_price': 0.0,  # CLOSE注文では不要（バリデーション用）
            'sl_price': 0.0,  # CLOSE注文では不要（バリデーション用）
            'comment': 'Streamlit_Position_Close'
        }
        
        # SQS送信（注文と同じフロー）
        order_publisher = container.get_sqs_order_publisher()
        success, message_id = order_publisher.send_order(close_order_data)
        
        if success:
            st.session_state.position_action_result = {
                'success': True,
                'message': f"✅ ポジション #{ticket} の決済注文を送信しました（MessageID: {message_id[:16]}...）"
            }
            logger.info(f"Position close order sent via SQS: {ticket}, MessageID={message_id}")
        else:
            st.session_state.position_action_result = {
                'success': False,
                'message': f"❌ 決済注文送信に失敗しました: {message_id}"
            }
            logger.error(f"Position close SQS send failed: {ticket}, error={message_id}")
        
        # 選択状態をクリア
        st.session_state.selected_position_ticket = None
        st.rerun()
        
    except Exception as e:
        st.session_state.position_action_result = {
            'success': False,
            'message': f"❌ 決済処理エラー: {str(e)}"
        }
        logger.error(f"Exception during position close: {e}", exc_info=True)
        st.rerun()


def _render_trade_history(account_provider = None):
    """取引履歴の表示（将来実装）"""
    st.markdown("#### 📜 本日の取引履歴")
    
    # Phase 2実装予定: MT5履歴API利用
    # history_deals = mt5.history_deals_get(today_start, now)
    
    # 暫定表示
    st.info("📋 取引履歴機能は Phase 2で実装予定")
    st.caption("MT5の履歴APIを使用してリアルタイム取引履歴を表示します")


# ユーティリティ関数
def _format_currency(amount: float) -> str:
    """通貨フォーマット"""
    return f"¥{amount:+,.0f}"


def _format_percentage(value: float) -> str:
    """パーセンテージフォーマット"""
    return f"{value:+.2f}%"


def _get_pnl_color(pnl: float) -> str:
    """損益に基づく色判定"""
    if pnl > 0:
        return "normal"
    elif pnl < 0:
        return "inverse"
    else:
        return "off"


# エラーハンドリング付きのキャッシュクリア
def clear_position_cache():
    """ポジションキャッシュをクリア"""
    try:
        # Streamlitキャッシュクリア
        if hasattr(st, 'cache_data'):
            st.cache_data.clear()
        
        logger.info("Position cache cleared")
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")


# セッション状態管理
def initialize_session_state():
    """セッション状態初期化"""
    if 'last_position_refresh' not in st.session_state:
        st.session_state.last_position_refresh = None
    
    if 'selected_position' not in st.session_state:
        st.session_state.selected_position = None


# ページエントリーポイント
if __name__ == "__main__":
    # デバッグ用ローカル実行
    initialize_session_state()
    render_position_page()