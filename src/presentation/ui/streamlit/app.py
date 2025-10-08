# src/presentation/ui/streamlit/app.py

import streamlit as st
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

# モジュールインポート
from services.dynamodb_service import DynamoDBService
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
    
    # DynamoDBサービスの初期化
    db = init_services()
    
    # Kill Switch状態の取得
    kill_switch_status = db.get_kill_switch_status()
    
    # サイドバーレンダリング
    render_sidebar(db, kill_switch_status)
    
    # ヘッダーメトリクス表示
    render_header_metrics()
    
    # メインタブ
    chart_tab, position_tab, signal_tab, analysis_tab = st.tabs([
        "📊 チャート", 
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


@st.cache_resource
def init_services():
    """サービスの初期化（キャッシュ付き）"""
    return DynamoDBService()


if __name__ == "__main__":
    main()