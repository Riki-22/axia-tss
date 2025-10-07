# src/presentation/ui/streamlit/config/styles.py

def get_custom_css() -> str:
    """カスタムCSSスタイルを返す"""
    return """
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
    
    /* BUYボタン */
    div[data-testid="stButton"] button:contains("BUY") {
        background: linear-gradient(135deg, #4CAF50, #45a049) !important;
        border: 2px solid #4CAF50 !important;
    }
    
    /* SELLボタン */
    div[data-testid="stButton"] button:contains("SELL") {
        background: linear-gradient(135deg, #f44336, #da190b) !important;
        border: 2px solid #f44336 !important;
    }
    
    /* 注文実行ボタン */
    div[data-testid="stButton"] button:contains("注文実行") {
        background: linear-gradient(135deg, #FFD700, #FFA000) !important;
        color: #000 !important;
        font-weight: bold !important;
        font-size: 18px !important;
        padding: 15px !important;
    }
    
    /* 成功系の色統一 */
    .stSuccess, div[data-testid="stMarkdownContainer"] .success {
        background: linear-gradient(135deg, #4CAF50, #45a049) !important;
    }
    
    /* エラー系の色統一 */
    .stError, div[data-testid="stMarkdownContainer"] .error {
        background: linear-gradient(135deg, #f44336, #da190b) !important;
    }
    
    /* BUY/SELLボタンのホバー効果 */
    button:hover:contains("BUY") {
        transform: scale(1.1) !important;
        box-shadow: 0 0 20px rgba(76, 175, 80, 0.6) !important;
    }
    
    button:hover:contains("SELL") {
        transform: scale(1.1) !important;
        box-shadow: 0 0 20px rgba(244, 67, 54, 0.6) !important;
    }
</style>
"""