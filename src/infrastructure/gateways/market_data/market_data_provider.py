# src/infrastructure/gateways/market_data/market_data_provider.py
"""統合マーケットデータプロバイダー"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
import pandas as pd
import pytz

from src.infrastructure.persistence.redis.price_cache_repository import PriceCacheRepository
from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
from src.infrastructure.persistence.s3.market_data_repository import S3MarketDataRepository

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """
    統合マーケットデータプロバイダー
    
    責務:
        - ユースケース別の最適ソース選択
        - フォールバック戦略の実行
        - キャッシュ管理（Redisへの自動保存）
        - 統計情報の収集
        - エラーハンドリング
    """
    
    # タイムフレーム別の1日あたりのbar数（概算）
    BARS_PER_DAY = {
        'M1': 1440,   # 1分足: 24時間 × 60分
        'M5': 288,    # 5分足: 24時間 × 12
        'M15': 96,    # 15分足: 24時間 × 4
        'M30': 48,    # 30分足: 24時間 × 2
        'H1': 24,     # 1時間足: 24時間
        'H4': 6,      # 4時間足: 24時間 / 4
        'D1': 1,      # 日足: 1日
    }
    
    def __init__(
        self,
        price_cache: PriceCacheRepository,
        mt5_data_collector: Optional[MT5DataCollector] = None,
        s3_repository: Optional[S3MarketDataRepository] = None,
        yfinance_client: Optional[Any] = None
    ):
        """
        Args:
            price_cache: Redisキャッシュ（必須）
            mt5_data_collector: MT5データ収集器（オプション）
            s3_repository: S3リポジトリ（オプション）
            yfinance_client: yfinanceクライアント（オプション）
        """
        self.cache = price_cache
        self.mt5 = mt5_data_collector
        self.s3 = s3_repository
        self.yfinance = yfinance_client
        
        # 統計情報
        self._stats = {
            'total_requests': 0,
            'source_usage': {
                'redis': 0,
                'mt5': 0,
                's3': 0,
                'yfinance': 0
            },
            'response_times': {
                'redis': [],
                'mt5': [],
                's3': [],
                'yfinance': []
            },
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info("MarketDataProvider initialized")
        logger.info(f"Available sources: "
                   f"redis={self.cache is not None}, "
                   f"mt5={self.mt5 is not None}, "
                   f"s3={self.s3 is not None}, "
                   f"yfinance={self.yfinance is not None}")
    
    # ========================================
    # ソース優先順位決定
    # ========================================
    
    def _get_source_priority(
        self,
        use_case: str,
        period_days: int,
        force_source: Optional[str] = None
    ) -> List[str]:
        """
        ユースケースと期間から優先順位を決定
        
        Args:
            use_case: ユースケース
                - 'trading': リアルタイム取引
                - 'chart': チャート表示
                - 'analysis': 分析・バックテスト
            period_days: 取得日数
            force_source: 強制使用するソース（デバッグ用）
        
        Returns:
            List[str]: ソース名のリスト（優先順位順）
        
        優先順位マトリックス:
            trading (24h以内):  ['mt5', 'redis', 'yfinance']
            trading (24h超):    ['mt5', 'yfinance']
            
            chart (24h以内):    ['redis', 'mt5', 'yfinance']
            chart (24h超):      ['redis', 's3', 'yfinance']
            
            analysis (24h以内): ['redis', 's3', 'yfinance']
            analysis (24h超):   ['s3', 'redis', 'yfinance']
        
        Example:
            # trading用、24時間以内
            sources = provider._get_source_priority('trading', 1)
            # → ['mt5', 'redis', 'yfinance']
            
            # chart用、30日分
            sources = provider._get_source_priority('chart', 30)
            # → ['redis', 's3', 'yfinance']
        """
        # force_source指定時はそれのみ
        if force_source:
            logger.debug(f"Forcing source: {force_source}")
            return [force_source]
        
        # 期間判定
        is_recent = period_days <= 1  # 24時間以内
        
        logger.debug(
            f"Determining source priority: "
            f"use_case={use_case}, period_days={period_days}, "
            f"is_recent={is_recent}"
        )
        
        # ユースケース別優先順位マトリックス
        if use_case == 'trading':
            if is_recent:
                # リアルタイム取引: MT5優先
                priority = ['mt5', 'redis', 'yfinance']
            else:
                # 長期データ: MT5のみ（S3スキップ）
                priority = ['mt5', 'yfinance']
        
        elif use_case == 'chart':
            if is_recent:
                # 直近チャート: Redis優先
                priority = ['redis', 'mt5', 'yfinance']
            else:
                # 長期チャート: Redis → S3
                priority = ['redis', 's3', 'yfinance']
        
        elif use_case == 'analysis':
            if is_recent:
                # 直近分析: Redis → S3
                priority = ['redis', 's3', 'yfinance']
            else:
                # 長期分析: S3優先
                priority = ['s3', 'redis', 'yfinance']
        
        else:
            # デフォルト: 全ソース試行
            logger.warning(
                f"Unknown use_case '{use_case}', using default priority"
            )
            priority = ['redis', 'mt5', 's3', 'yfinance']
        
        # 利用可能なソースのみフィルタ
        available_priority = self._filter_available_sources(priority)
        
        logger.debug(
            f"Source priority for {use_case} ({period_days}d): "
            f"{available_priority}"
        )
        
        return available_priority
    
    def _filter_available_sources(self, sources: List[str]) -> List[str]:
        """
        利用可能なソースのみフィルタリング
        
        Args:
            sources: ソース名のリスト
        
        Returns:
            List[str]: 利用可能なソースのみのリスト
        """
        available = []
        
        for source in sources:
            if source == 'redis' and self.cache:
                available.append(source)
            elif source == 'mt5' and self.mt5:
                available.append(source)
            elif source == 's3' and self.s3:
                available.append(source)
            elif source == 'yfinance' and self.yfinance:
                available.append(source)
        
        if not available:
            logger.warning(
                f"No sources available from requested: {sources}"
            )
        
        return available
    
    def get_stats(self) -> Dict[str, Any]:
        """
        統計情報を取得
        
        Returns:
            Dict: 統計情報
        """
        # 平均レスポンス時間を計算
        avg_response_times = {}
        for source, times in self._stats['response_times'].items():
            if times:
                avg_response_times[source] = sum(times) / len(times)
            else:
                avg_response_times[source] = 0.0
        
        # キャッシュヒット率を計算
        total_cache_requests = (
            self._stats['cache_hits'] + self._stats['cache_misses']
        )
        cache_hit_rate = (
            self._stats['cache_hits'] / total_cache_requests
            if total_cache_requests > 0 else 0.0
        )
        
        return {
            'total_requests': self._stats['total_requests'],
            'source_usage': self._stats['source_usage'].copy(),
            'avg_response_time': avg_response_times,
            'cache_hit_rate': cache_hit_rate,
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses']
        }
    
    def reset_stats(self):
        """統計情報をリセット"""
        self._stats = {
            'total_requests': 0,
            'source_usage': {
                'redis': 0,
                'mt5': 0,
                's3': 0,
                'yfinance': 0
            },
            'response_times': {
                'redis': [],
                'mt5': [],
                's3': [],
                'yfinance': []
            },
            'cache_hits': 0,
            'cache_misses': 0
        }
        logger.info("Statistics reset")
    
    # ========================================
    # ソース別データ取得
    # ========================================
    
    def _days_to_bars(self, days: int, timeframe: str) -> int:
        """
        日数をbar数に変換（MT5用）
        
        Args:
            days: 日数
            timeframe: タイムフレーム
        
        Returns:
            int: bar数
        """
        bars_per_day = self.BARS_PER_DAY.get(timeframe, 24)
        
        # FX市場は土日休場を考慮（平日のみ）
        # 概算: 7日分 → 5日分
        actual_days = days * (5 / 7)
        
        bars = int(actual_days * bars_per_day)
        
        # 最低でも1本は取得
        return max(bars, 1)
    
    def _fetch_from_redis(
        self,
        symbol: str,
        timeframe: str,
        period_days: int
    ) -> Optional[pd.DataFrame]:
        """
        Redisからデータ取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            period_days: 取得日数
        
        Returns:
            pd.DataFrame or None
        """
        try:
            df = self.cache.load_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                days=period_days
            )
            
            if df is not None and not df.empty:
                logger.info(
                    f"Redis hit: {symbol} {timeframe}, {len(df)} rows"
                )
                return df
            else:
                logger.debug(
                    f"Redis miss: {symbol} {timeframe}"
                )
                return None
                
        except Exception as e:
            logger.error(f"Error fetching from Redis: {e}", exc_info=True)
            return None
    
    def _fetch_from_mt5(
        self,
        symbol: str,
        timeframe: str,
        period_days: int
    ) -> Optional[pd.DataFrame]:
        """
        MT5からデータ取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            period_days: 取得日数
        
        Returns:
            pd.DataFrame or None
        """
        try:
            # 日数をbar数に変換
            bars = self._days_to_bars(period_days, timeframe)
            
            logger.info(
                f"Fetching from MT5: {symbol} {timeframe}, "
                f"{period_days} days ({bars} bars)"
            )
            
            df = self.mt5.fetch_ohlcv_data(
                symbol=symbol,
                timeframe=timeframe,
                count=bars
            )
            
            if df is not None and not df.empty:
                logger.info(
                    f"MT5 success: {symbol} {timeframe}, {len(df)} rows"
                )
                return df
            else:
                logger.warning(
                    f"MT5 returned empty data: {symbol} {timeframe}"
                )
                return None
                
        except Exception as e:
            logger.error(f"Error fetching from MT5: {e}", exc_info=True)
            return None
    
    def _fetch_from_s3(
        self,
        symbol: str,
        timeframe: str,
        period_days: int
    ) -> Optional[pd.DataFrame]:
        """
        S3からデータ取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            period_days: 取得日数
        
        Returns:
            pd.DataFrame or None
        """
        try:
            logger.info(
                f"Fetching from S3: {symbol} {timeframe}, "
                f"{period_days} days"
            )
            
            df = self.s3.load_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                days=period_days
            )
            
            if df is not None and not df.empty:
                logger.info(
                    f"S3 success: {symbol} {timeframe}, {len(df)} rows"
                )
                return df
            else:
                logger.warning(
                    f"S3 returned empty data: {symbol} {timeframe}"
                )
                return None
                
        except Exception as e:
            logger.error(f"Error fetching from S3: {e}", exc_info=True)
            return None
    
    def _fetch_from_yfinance(
        self,
        symbol: str,
        timeframe: str,
        period_days: int
    ) -> Optional[pd.DataFrame]:
        """
        yfinanceからデータ取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            period_days: 取得日数
        
        Returns:
            pd.DataFrame or None
        
        Note:
            Phase 2では最小限の実装。Phase 3で詳細実装予定。
        """
        try:
            logger.info(
                f"Fetching from yfinance: {symbol} {timeframe}, "
                f"{period_days} days"
            )
            
            # yfinanceクライアントが利用可能か確認
            if self.yfinance is None:
                logger.warning("yfinance client not available")
                return None
            
            # yfinance実装（最小限）
            # TODO: Phase 3で詳細実装
            logger.warning("yfinance fetch not fully implemented yet")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching from yfinance: {e}", exc_info=True)
            return None
    
    def _fetch_from_source(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        period_days: int
    ) -> Optional[pd.DataFrame]:
        """
        指定されたソースからデータを取得
        
        Args:
            source: データソース名 ('redis', 'mt5', 's3', 'yfinance')
            symbol: 通貨ペア
            timeframe: タイムフレーム
            period_days: 取得日数
        
        Returns:
            pd.DataFrame: OHLCVデータ
            None: データ取得失敗
        """
        if source == 'redis':
            return self._fetch_from_redis(symbol, timeframe, period_days)
        
        elif source == 'mt5':
            return self._fetch_from_mt5(symbol, timeframe, period_days)
        
        elif source == 's3':
            return self._fetch_from_s3(symbol, timeframe, period_days)
        
        elif source == 'yfinance':
            return self._fetch_from_yfinance(symbol, timeframe, period_days)
        
        else:
            logger.warning(f"Unknown source: {source}")
            return None
    
    # ========================================
    # メインAPI
    # ========================================
    
    def get_data(
        self,
        symbol: str,
        timeframe: str,
        period_days: int = 1,
        use_case: str = 'trading',
        force_source: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
        """
        マーケットデータを取得（メインAPI）
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
            timeframe: タイムフレーム（例: 'H1'）
            period_days: 取得日数（デフォルト: 1日）
            use_case: ユースケース
                - 'trading': リアルタイム取引
                - 'chart': チャート表示
                - 'analysis': 分析・バックテスト
            force_source: 強制使用するソース（デバッグ用）
                - 'redis' / 'mt5' / 's3' / 'yfinance'
        
        Returns:
            Tuple[DataFrame, metadata]:
                DataFrame: OHLCVデータ（失敗時None）
                metadata: {
                    'source': str,           # 使用したソース
                    'response_time': float,  # レスポンス時間（秒）
                    'row_count': int,        # データ行数
                    'cache_hit': bool,       # キャッシュヒット
                    'fallback_count': int,   # フォールバック回数
                    'error': str            # エラーメッセージ（あれば）
                }
        
        Example:
            >>> provider = MarketDataProvider(...)
            >>> 
            >>> # リアルタイム取引用（24時間）
            >>> df, meta = provider.get_data('USDJPY', 'H1', 1, 'trading')
            >>> 
            >>> # チャート表示用（30日）
            >>> df, meta = provider.get_data('USDJPY', 'H1', 30, 'chart')
            >>> 
            >>> # デバッグ: S3を強制使用
            >>> df, meta = provider.get_data(
            ...     'USDJPY', 'H1', 30, force_source='s3'
            ... )
        """
        start_time = time.time()
        fallback_count = 0
        
        # 統計情報更新
        self._stats['total_requests'] += 1
        
        logger.info(
            f"Data request: {symbol} {timeframe}, "
            f"{period_days} days, use_case={use_case}"
        )
        
        # Step 1: 優先順位決定
        sources = self._get_source_priority(
            use_case, period_days, force_source
        )
        
        # 利用可能なソースのみにフィルタリング
        available_sources = self._filter_available_sources(sources)
        
        if not available_sources:
            error_msg = "No data sources available"
            logger.error(error_msg)
            return None, {
                'error': error_msg,
                'response_time': time.time() - start_time,
                'fallback_count': 0
            }
        
        logger.info(f"Source priority: {available_sources}")
        
        # Step 2: 各ソースを順次試行
        for source in available_sources:
            source_start = time.time()
            
            logger.info(f"Trying source: {source}")
            
            df = self._fetch_from_source(
                source, symbol, timeframe, period_days
            )
            
            source_time = time.time() - source_start
            
            if df is not None and not df.empty:
                # Step 3: 成功時の処理
                
                # 統計情報更新
                self._update_stats(source, source_time, success=True)
                
                # Redisキャッシュ（redis以外から取得した場合）
                if source != 'redis':
                    self._cache_result(df, symbol, timeframe)
                    self._stats['cache_misses'] += 1
                else:
                    self._stats['cache_hits'] += 1
                
                # metadata生成
                total_time = time.time() - start_time
                metadata = {
                    'source': source,
                    'response_time': total_time,
                    'row_count': len(df),
                    'cache_hit': source == 'redis',
                    'fallback_count': fallback_count
                }
                
                logger.info(
                    f"Data fetch success: source={source}, "
                    f"rows={len(df)}, time={total_time:.3f}s"
                )
                
                return df, metadata
            
            else:
                # 失敗時
                self._update_stats(source, source_time, success=False)
                fallback_count += 1
                logger.warning(
                    f"Source {source} failed, trying next source"
                )
        
        # Step 4: 全ソース失敗
        total_time = time.time() - start_time
        error_msg = f"All data sources failed for {symbol} {timeframe}"
        logger.error(error_msg)
        
        return None, {
            'error': error_msg,
            'response_time': total_time,
            'fallback_count': fallback_count
        }
    
    def _cache_result(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ):
        """
        取得したデータをRedisに自動キャッシュ
        
        Args:
            df: OHLCVデータ
            symbol: 通貨ペア
            timeframe: タイムフレーム
        
        ルール:
            - 最新24時間分のみキャッシュ
            - それ以前のデータは破棄
            - キャッシュ失敗はログ記録のみ（例外を投げない）
        """
        try:
            # 24時間分にフィルタリング
            cutoff = datetime.now(pytz.UTC) - timedelta(hours=24)
            df_recent = df[df.index >= cutoff]
            
            if len(df_recent) > 0:
                # PriceCacheに保存を委譲
                success = self.cache.save_ohlcv(
                    df_recent, symbol, timeframe
                )
                
                if success:
                    logger.info(
                        f"Auto-cached {len(df_recent)} rows "
                        f"for {symbol} {timeframe}"
                    )
                else:
                    logger.warning(
                        f"Failed to cache {symbol} {timeframe}"
                    )
            else:
                logger.debug(
                    f"No recent data to cache for {symbol} {timeframe}"
                )
        
        except Exception as e:
            # キャッシュ失敗してもデータ取得は成功扱い
            logger.warning(
                f"Exception during auto-cache: {e}",
                exc_info=True
            )
    
    def _update_stats(
        self,
        source: str,
        response_time: float,
        success: bool
    ):
        """
        統計情報を更新
        
        Args:
            source: データソース名
            response_time: レスポンス時間（秒）
            success: 成功フラグ
        """
        if success:
            self._stats['source_usage'][source] += 1
            self._stats['response_times'][source].append(response_time)