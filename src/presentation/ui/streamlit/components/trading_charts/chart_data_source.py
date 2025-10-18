# src/presentation/ui/streamlit/components/trading_charts/chart_data_source.py

import streamlit as st
import pandas as pd
import logging
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# OhlcvDataProviderのインポート
try:
    from src.infrastructure.di.container import DIContainer
    PROVIDER_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import DIContainer: {e}")
    PROVIDER_AVAILABLE = False


class ChartDataSource:
    """
    チャートデータ取得クラス
    
    責務:
    - OhlcvDataProviderを使用した統合データ取得
    - Streamlitキャッシュ管理
    - データソース情報の提供
    
    変更点（旧実装から）:
    - YFinanceGatewayの直接使用 → OhlcvDataProvider経由
    - ダミーデータ生成削除 → OhlcvDataProviderのフォールバックに任せる
    - キャッシュ戦略の簡素化
    """
    
    def __init__(self):
        """初期化"""
        self.provider_available = PROVIDER_AVAILABLE
        self.data_provider = None
        
        if PROVIDER_AVAILABLE:
            try:
                container = DIContainer()
                self.data_provider = container.get_ohlcv_data_provider()
                logger.info("ChartDataSource initialized with OhlcvDataProvider")
            except Exception as e:
                logger.error(f"Failed to initialize OhlcvDataProvider: {e}")
                self.data_provider = None
        else:
            logger.warning("DIContainer not available, ChartDataSource in fallback mode")
    
    def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str,
        period_days: int = 30
    ) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
        """
        OHLCVデータを取得（Streamlitキャッシュ付き）
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間足
            period_days: 取得日数
        
        Returns:
            Tuple[DataFrame, metadata]:
                DataFrame: OHLCVデータ（失敗時None）
                metadata: {
                    'source': str,
                    'cache_hit': bool,
                    'data_age': float,
                    'fresh': bool,
                    'response_time': float,
                    'row_count': int
                }
        """
        if not self.data_provider:
            return None, {
                'error': 'Data provider not available',
                'source': 'none'
            }
        
        try:
            # OhlcvDataProviderからデータ取得
            df, metadata = self.data_provider.get_data(
                symbol=symbol,
                timeframe=timeframe,
                period_days=period_days,
                use_case='chart'
            )
            
            if df is None or df.empty:
                logger.warning(f"No data available: {symbol} {timeframe}")
                return None, metadata
            
            # time列をインデックスに変換（チャート描画用）
            if 'time' in df.columns:
                df = df.set_index('time')
                logger.debug(f"Set 'time' as index for chart rendering")
            
            # メタデータ更新
            metadata['rows'] = len(df)
            
            logger.info(
                f"Data loaded: {symbol} {timeframe}, "
                f"source={metadata.get('source')}, rows={len(df)}, "
                f"fresh={metadata.get('fresh', False)}"
            )
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}", exc_info=True)
            return None, {'error': str(e)}
    
    def force_refresh(
        self,
        symbol: str,
        timeframe: str,
        period_days: int = 30
    ) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
        """
        キャッシュをクリアして強制的に最新データを取得
        
        処理フロー:
        1. Streamlitキャッシュをクリア
        2. force_source='mt5'でMT5から強制取得
        3. 取得データは自動的にRedisにキャッシュされる
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間足
            period_days: 取得日数
        
        Returns:
            Tuple[DataFrame, metadata]
        """
        if not self.data_provider:
            return None, {
                'error': 'Data provider not available',
                'source': 'none'
            }
        
        try:
            logger.info(
                f"Force refresh requested: {symbol} {timeframe}"
            )
            
            # Streamlitキャッシュをクリア
            st.cache_data.clear()
            
            # MT5から強制取得
            df, metadata = self.data_provider.get_data_with_freshness(
                symbol=symbol,
                timeframe=timeframe,
                period_days=period_days,
                use_case='chart',
                force_source='mt5'  # ★MT5から強制取得
            )
            
            if df is None or df.empty:
                logger.warning(
                    f"Force refresh failed: {symbol} {timeframe}"
                )
                return None, metadata
            
            logger.info(
                f"Force refresh success: {symbol} {timeframe}, "
                f"source={metadata.get('source')}, "
                f"rows={len(df)}"
            )
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"Error in force_refresh: {e}", exc_info=True)
            return None, {'error': str(e)}
    
    def get_data_source_info(self) -> str:
        """
        データソース情報を取得
        
        Returns:
            str: データソース名
        """
        if self.data_provider:
            return "OhlcvDataProvider (Redis/MT5/S3/yfinance)"
        else:
            return "Not Available"
    
    def is_available(self) -> bool:
        """
        データプロバイダーが利用可能かチェック
        
        Returns:
            bool: 利用可能な場合True
        """
        return self.data_provider is not None


# ========================================
# シングルトン取得関数
# ========================================

@st.cache_resource
def get_chart_data_source() -> ChartDataSource:
    """
    ChartDataSourceのシングルトンインスタンスを取得
    
    この関数はStreamlitの@cache_resourceデコレータにより、
    アプリケーション全体で1つのインスタンスのみが生成される。
    
    Returns:
        ChartDataSource: チャートデータソースインスタンス
    
    Usage:
        >>> from chart_data_source import get_chart_data_source
        >>> data_source = get_chart_data_source()
        >>> df, meta = data_source.get_ohlcv_data('USDJPY', 'H1', days=30)
    """
    logger.info("Initializing ChartDataSource singleton")
    return ChartDataSource()


# ========================================
# 後方互換性のための関数（既存コードをサポート）
# ========================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_data(
    symbol: str,
    timeframe: str,
    period_days: int = 30
) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    """
    市場データ取得（後方互換性のための関数）
    
    注意: 新しいコードではget_chart_data_source().get_ohlcv_data()を使用してください
    
    Args:
        symbol: 通貨ペア
        timeframe: 時間足
        period_days: 取得日数
    
    Returns:
        Tuple[DataFrame, metadata]
    """
    data_source = get_chart_data_source()
    return data_source.get_ohlcv_data(symbol, timeframe, period_days)