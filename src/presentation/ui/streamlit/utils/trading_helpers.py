# src/presentation/ui/streamlit/utils/trading_helpers.py

import streamlit as st
from typing import List


def get_column_config() -> List[int]:
    """画面サイズに応じたカラム設定
    
    Returns:
        カラム数のリスト
    """
    # モバイル向けは1カラム、デスクトップは多カラム
    if st.session_state.get('mobile_view', False):
        return [1]  # 1カラム
    else:
        return [1, 1, 1, 1, 1, 1]  # 6カラム