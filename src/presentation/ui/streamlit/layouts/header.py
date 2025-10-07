# src/presentation/ui/streamlit/layouts/header.py

import streamlit as st


def render_header_metrics():
    """ヘッダーメトリクスの表示"""
    st.markdown("## AXIA - Trading Strategy System -")
    
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