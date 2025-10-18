# src/presentation/ui/streamlit/layouts/sidebar.py

import streamlit as st
from datetime import datetime
from typing import Dict, Any


def render_sidebar(db_service, kill_switch_status: Dict[str, Any]):
    """サイドバーのレンダリング
    
    Args:
        db_service: DynamoDBサービスインスタンス
        kill_switch_status: Kill Switch状態の辞書
    """
    with st.sidebar:
        _render_system_status(kill_switch_status)
        _render_db_connection_status(db_service)
        _render_control_panel()
        _render_kill_switch_controls(db_service, kill_switch_status)


def _render_system_status(kill_switch_status: Dict[str, Any]):
    """システムステータスの表示"""
    st.markdown("#### 💓 システムステータス")
    
    if kill_switch_status.get('active'):
        st.error("🚨 **KILL SWITCH ACTIVE** - 全取引停止中")
        st.caption(f"最終更新: {kill_switch_status.get('last_updated', 'N/A')}")
    else:
        st.success("✅ システム正常稼働中")


def _render_db_connection_status(db_service):
    """DB接続状態の表示"""
    conn_test = db_service.test_connection()
    if conn_test['status'] == 'SUCCESS':
        st.success(f"✅ DB接続: {conn_test['table']}")
    else:
        st.error("❌ DB接続エラー")
        st.caption(conn_test.get('error', 'Unknown error'))
    
    if st.button("🔄 リロード", key="refresh"):
        st.rerun()

    st.caption(f"最終確認: {datetime.now().strftime('%H:%M:%S')}")


def _render_control_panel():
    """コントロールパネルの表示"""
    st.markdown("---")
    st.markdown("#### ⚙️ コントロールパネル")
    
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


def _render_kill_switch_controls(db_service, kill_switch_status: Dict[str, Any]):
    """Kill Switchコントロールの表示"""
    st.markdown("---")
    with st.container():
        st.markdown("#### 🚨 緊急停止")
        
        current_status = kill_switch_status.get('status', 'OFF')
        if current_status == 'ON':
            if st.button("🔓 **Kill Switch 解除**", type="secondary", width='stretch'):
                result = db_service.set_kill_switch('OFF')
                if result['success']:
                    st.success("Kill Switch を解除しました")
                    st.rerun()
                else:
                    st.error(f"エラー: {result.get('error')}")
        else:
            if st.button("🛑 **KILL SWITCH 発動**", type="primary", width='stretch'):
                result = db_service.set_kill_switch('ON')
                if result['success']:
                    st.warning("Kill Switch を発動しました")
                    st.rerun()
                else:
                    st.error(f"エラー: {result.get('error')}")
        
        st.checkbox("全ポジション決済", key="ks1")
        st.checkbox("全注文キャンセル", key="ks2")
        st.checkbox("新規取引停止", key="ks3")