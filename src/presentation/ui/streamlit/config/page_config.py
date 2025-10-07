# src/presentation/ui/streamlit/config/page_config.py

import streamlit as st

def setup_page_config():
    """Streamlitページの基本設定"""
    st.set_page_config(
        page_title="AXIA - Trading Strategy System -", 
        page_icon="📊",
        layout="wide",  # 常にwideモードを使用
        # initial_sidebar_state="collapsed"  # 初期状態でサイドバーを閉じる
    )

def get_column_config():
    """画面サイズに応じたカラム設定"""
    # モバイル向けは1カラム、デスクトップは多カラム
    if st.session_state.get('mobile_view', False):
        return [1]  # 1カラム
    else:
        return [1, 1, 1, 1, 1, 1]  # 6カラム