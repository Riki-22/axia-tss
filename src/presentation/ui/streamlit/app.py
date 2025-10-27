# src/presentation/ui/streamlit/app.py

import streamlit as st
import sys
import logging

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Plotly警告を抑制（UIに表示させない）
import warnings
warnings.filterwarnings('ignore', message='.*keyword arguments have been deprecated.*')
warnings.filterwarnings('ignore', message='.*will be removed in a future release.*')
warnings.filterwarnings('ignore', category=FutureWarning, module='plotly')
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', module='plotly')

# StreamlitでPlotly警告を非表示
import plotly.io as pio
pio.templates.default = "plotly"

# Streamlit設定で警告抑制
import os
os.environ['STREAMLIT_LOGGER_LEVEL'] = 'ERROR'

from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

if project_root.exists():
    load_dotenv(dotenv_path=project_root/'.env')

# モジュールインポート
from src.presentation.ui.streamlit.controllers.system_controller import get_system_controller
from config import setup_page_config, get_custom_css
from layouts import render_sidebar, render_header_metrics
from pages import (
    render_trading_page,
    render_position_page,
    render_signal_page,
    render_analysis_page
)


def main():
    """メインアプリケーション"""
    
    # ページ設定
    setup_page_config()
    
    # カスタムCSS適用
    st.markdown(get_custom_css(), unsafe_allow_html=True)
    
    # システムコントローラー初期化
    db = get_system_controller()
    
    # Kill Switch状態の取得
    kill_switch_status = db.get_kill_switch_status()
    
    # サイドバーレンダリング
    render_sidebar(db, kill_switch_status)
    
    # ヘッダーメトリクス表示
    render_header_metrics()
    
    # メインタブ
    chart_tab, position_tab, signal_tab, analysis_tab = st.tabs([
        "📊 トレード", 
        "📂 ポジション",
        "⚡ シグナル", 
        "📝 分析"
    ])
    
    with chart_tab:
        render_trading_page()
    
    with position_tab:
        render_position_page()
    
    with signal_tab:
        render_signal_page()
    
    with analysis_tab:
        render_analysis_page()



if __name__ == "__main__":
    main()