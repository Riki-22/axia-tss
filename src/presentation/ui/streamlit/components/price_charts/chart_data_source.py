# src/presentation/ui/streamlit/components/price_charts/chart_data_source.py

import streamlit as st
import pandas as pd
from datetime import datetime
import logging
from typing import Optional
import sys
from pathlib import Path

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Market Dataクライアントのインポート
try:
    from src.infrastructure.gateways.market_data.yfinance_gateway import YFinanceGateway
    YFINANCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"YFinance client not available: {e}")
    YFINANCE_AVAILABLE = False

# ダミーデータジェネレーターのインポート
from src.infrastructure.gateways.market_data.dummy_generator import DummyMarketDataGenerator


class ChartDataSource:
    """チャートデータ取得を担当するクラス"""
    
    def __init__(self, cache_duration: int = 300):
        """
        Args:
            cache_duration: キャッシュ期間（秒）
        """
        self.cache_duration = cache_duration
        self.use_real_data = YFINANCE_AVAILABLE
        
        if self.use_real_data:
            self.data_client = YFinanceGateway(cache_duration=cache_duration)
        else:
            self.data_client = None
            logger.info("Using dummy data mode (YFinance not available)")
    
    @st.cache_data(ttl=300)
    def fetch_market_data(symbol: str, timeframe: str, period: str = '1mo', use_real: bool = True) -> pd.DataFrame:
        """
        市場データ取得（静的メソッド、Streamlitキャッシュ付き）
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            period: 取得期間
            use_real: 実データ使用フラグ
        
        Returns:
            pd.DataFrame: OHLCVデータ
        """
        if use_real and YFINANCE_AVAILABLE:
            try:
                client = YFinanceGateway(cache_duration=300)
                df = client.fetch_ohlcv(symbol, timeframe, period=period)
                
                if not df.empty:
                    logger.info(f"実データ取得成功: {symbol} {timeframe} - {len(df)}件")
                    return df
                else:
                    logger.warning(f"データ取得失敗、ダミーデータを使用: {symbol}")
                    return ChartDataSource.generate_dummy_data(30, timeframe)
                    
            except Exception as e:
                logger.error(f"データ取得エラー: {e}")
                return ChartDataSource.generate_dummy_data(30, timeframe)
        else:
            return ChartDataSource.generate_dummy_data(30, timeframe)
    
    def fetch_data(self, symbol: str, timeframe: str, days: int = 30) -> pd.DataFrame:
        """
        インスタンスメソッドとしてのデータ取得
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            days: 表示日数
        
        Returns:
            pd.DataFrame: OHLCVデータ
        """
        period = self.get_period_string(days)
        
        if self.use_real_data and self.data_client:
            try:
                df = self.data_client.fetch_ohlcv(symbol, timeframe, period=period)
                
                if not df.empty:
                    logger.info(f"実データ取得成功: {symbol} {timeframe} - {len(df)}件")
                    return df
                else:
                    logger.warning(f"データ取得失敗、ダミーデータを使用: {symbol}")
                    return self.generate_dummy_data(days, timeframe)
                    
            except Exception as e:
                logger.error(f"データ取得エラー: {e}")
                return self.generate_dummy_data(days, timeframe)
        else:
            return self.generate_dummy_data(days, timeframe)
    
    @staticmethod
    def get_period_string(days: int) -> str:
        """
        日数をYFinanceの期間文字列に変換
        
        Args:
            days: 日数
        
        Returns:
            str: 期間文字列（例: '1mo', '3mo'）
        """
        period_map = {
            7: '7d',
            14: '2wk',
            30: '1mo',
            60: '3mo',
            180: '6mo',
            365: '1y'
        }
        
        # 最も近い期間を選択
        for d in sorted(period_map.keys()):
            if days <= d:
                return period_map[d]
        return '1y'
    
    @staticmethod
    def generate_dummy_data(days: int, timeframe: str = 'H1') -> pd.DataFrame:
        """
        ダミーデータ生成（フォールバック用）
        
        Args:
            days: 生成する日数
            timeframe: 時間枠
        
        Returns:
            pd.DataFrame: ダミーのOHLCVデータ
        """
        generator = DummyMarketDataGenerator(seed=42)
        return generator.generate_ohlcv(
            days=days,
            timeframe=timeframe,
            base_price=150.0,
            volatility=0.5,
            trend=0.0
        )
    
    def get_data_source_info(self) -> str:
        """
        データソース情報を取得
        
        Returns:
            str: データソース名
        """
        if self.use_real_data and YFINANCE_AVAILABLE:
            return "Yahoo Finance"
        else:
            return "Dummy Data"
    
    def is_real_data_available(self) -> bool:
        """
        実データが利用可能かチェック
        
        Returns:
            bool: 利用可能な場合True
        """
        return self.use_real_data and YFINANCE_AVAILABLE