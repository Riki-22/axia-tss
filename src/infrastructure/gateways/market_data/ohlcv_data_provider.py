# src/infrastructure/gateways/market_data/ohlcv_data_provider.py
"""統合マーケットデータプロバイダー"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
import pandas as pd
import pytz

from src.domain.repositories.ohlcv_data_repository import IOhlcvDataRepository
from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector

logger = logging.getLogger(__name__)


class OhlcvDataProvider:
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
        ohlcv_cache: IOhlcvDataRepository,
        mt5_data_collector: Optional[MT5DataCollector] = None,
        s3_repository: Optional[IOhlcvDataRepository] = None,
        yfinance_client: Optional[Any] = None
    ):
        """
        Args:
            ohlcv_cache: Redisキャッシュ（必須）
            mt5_data_collector: MT5データ収集器（オプション）
            s3_repository: S3リポジトリ（オプション）
            yfinance_client: yfinanceクライアント（オプション）
        """
        self.cache = ohlcv_cache
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
        
        logger.info("OhlcvDataProvider initialized")
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
        yfinanceからデータを取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            period_days: 取得日数
        
        Returns:
            pd.DataFrame: OHLCVデータ
            None: 取得失敗
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
            
            # YFinanceGatewayのfetch_ohlcvメソッドを使用
            # 期間マッピング: 30日 → '1mo', 90日 → '3mo', 365日 → '1y'
            if period_days <= 7:
                period = '7d'
            elif period_days <= 30:
                period = '1mo'
            elif period_days <= 90:
                period = '3mo'
            elif period_days <= 180:
                period = '6mo'
            elif period_days <= 365:
                period = '1y'
            else:
                period = '2y'
            
            # YFinanceGateway.fetch_ohlcvを呼び出し
            df = self.yfinance.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                period=period
            )
            
            if df is None or df.empty:
                logger.warning(f"No data returned from yfinance: {symbol} {timeframe}")
                return None
            
            # YFinanceGatewayは既に標準OHLCV形式を返すが、
            # カラム名がインデックス+OHLCV形式なので、必要に応じて変換
            
            # インデックスを'time'カラムに変換（OhlcvDataProviderの標準形式）
            if 'time' not in df.columns and df.index.name is not None:
                df = df.reset_index()
                df.rename(columns={df.columns[0]: 'time'}, inplace=True)
            
            # カラム名の小文字化（念のため）
            df.columns = [col.lower() for col in df.columns]
            
            # 必要なカラムのみ抽出
            required_columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            available_columns = [col for col in required_columns if col in df.columns]
            
            if 'time' not in available_columns:
                logger.error(f"Missing 'time' column in yfinance data for {symbol}")
                return None
            
            df = df[available_columns]
            
            # period_daysでフィルタリング（yfinanceが多めに返す場合がある）
            if period_days and period_days > 0 and 'time' in df.columns:
                from datetime import datetime, timedelta
                import pytz
                
                cutoff = datetime.now(pytz.UTC) - timedelta(days=period_days)
                
                # time列をdatetimeに変換（必要な場合）
                if not pd.api.types.is_datetime64_any_dtype(df['time']):
                    df['time'] = pd.to_datetime(df['time'])
                
                # タイムゾーン処理
                if df['time'].dt.tz is None:
                    df['time'] = df['time'].dt.tz_localize(pytz.UTC)
                else:
                    df['time'] = df['time'].dt.tz_convert(pytz.UTC)
                
                # フィルタリング
                df = df[df['time'] >= cutoff]
            
            logger.info(
                f"Successfully fetched {len(df)} rows from yfinance: "
                f"{symbol} {timeframe}"
            )
            
            return df
            
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
            >>> provider = OhlcvDataProvider(...)
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
    ) -> None:
        """
        取得データをRedisに自動キャッシュ
        
        Args:
            df: OHLCVデータ（time列がインデックス想定）
            symbol: 通貨ペア
            timeframe: タイムフレーム
        
        ルール:
        - 最新24時間分のみ保存
        - 失敗しても例外を投げない（ログ記録のみ）
        """
        if self.ohlcv_cache is None:
            return
        
        try:
            from datetime import datetime, timedelta
            import pytz
            
            # DataFrameが空でないことを確認
            if df is None or df.empty:
                logger.debug("No data to cache (empty DataFrame)")
                return
            
            # インデックスがdatetime型であることを確認
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                logger.warning("Cannot cache: index is not datetime type")
                return
            
            # 24時間分にフィルタリング
            cutoff = datetime.now(pytz.UTC) - timedelta(hours=24)
            
            # インデックスのタイムゾーン処理
            if df.index.tz is None:
                # タイムゾーンなし → UTCとして扱う
                df_tz = df.copy()
                df_tz.index = df_tz.index.tz_localize(pytz.UTC)
            else:
                # タイムゾーンあり → UTCに変換
                df_tz = df.copy()
                df_tz.index = df_tz.index.tz_convert(pytz.UTC)
            
            # フィルタリング
            df_recent = df_tz[df_tz.index >= cutoff]
            
            if len(df_recent) == 0:
                logger.debug(
                    f"No recent data to cache for {symbol} {timeframe} "
                    f"(all data older than 24 hours)"
                )
                return
            
            # Redis保存（インデックスをtime列に戻す）
            df_to_save = df_recent.reset_index()
            df_to_save.rename(columns={'index': 'time'}, inplace=True)
            
            # RedisOhlcvDataRepositoryはtime列を期待
            success = self.ohlcv_cache.save_ohlcv(
                df_to_save,
                symbol,
                timeframe
            )
            
            if success:
                logger.info(
                    f"Cached {len(df_recent)} rows for {symbol} {timeframe}"
                )
            else:
                logger.warning(
                    f"Failed to cache data for {symbol} {timeframe}"
                )
            
        except Exception as e:
            # キャッシュ失敗してもデータ取得は成功扱い
            logger.warning(f"Cache save error (ignored): {e}", exc_info=True)
    
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

    # ========================================
    # 最大データエイジ取得
    # ========================================
    
    def _get_max_age(self, timeframe: str) -> timedelta:
        """
        時間足に応じた許容される最大データ年齢を取得
        
        短い時間足ほど頻繁な更新が必要:
        - M1/M5: 数分以内の最新データが必要
        - H1/H4: 数時間以内で許容
        - D1/W1: 1日〜1週間で許容
        
        Args:
            timeframe: 時間足（'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN1'）
        
        Returns:
            timedelta: 許容される最大データ年齢
        
        Example:
            >>> provider = OhlcvDataProvider(...)
            >>> max_age = provider._get_max_age('H1')
            >>> print(max_age)  # 2時間
        """
        age_map = {
            'M1': timedelta(minutes=5),    # 1分足: 5分以内
            'M5': timedelta(minutes=15),   # 5分足: 15分以内
            'M15': timedelta(minutes=30),  # 15分足: 30分以内
            'M30': timedelta(hours=1),     # 30分足: 1時間以内
            'H1': timedelta(hours=2),      # 1時間足: 2時間以内
            'H4': timedelta(hours=6),      # 4時間足: 6時間以内
            'D1': timedelta(days=1),       # 日足: 1日以内
            'W1': timedelta(days=7),       # 週足: 1週間以内
            'MN1': timedelta(days=30),     # 月足: 1ヶ月以内
        }
        
        return age_map.get(timeframe, timedelta(hours=1))  # デフォルト: 1時間
    
    # ========================================
    # get_data更新（鮮度チェック付き）
    # ========================================
    
    def get_data_with_freshness(
        self,
        symbol: str,
        timeframe: str,
        period_days: int = 1,
        use_case: str = 'trading',
        force_source: str | None = None
    ) -> tuple:
        """
        マーケットデータを取得（鮮度チェック付き）
        
        処理フロー:
        1. Redisキャッシュをチェック（利用可能な場合）
        2. データが存在し、かつ新鮮な場合 → 即座に返却
        3. データが古い、または存在しない場合 → 他ソースから取得
        4. 取得成功時 → Redisに自動保存（利用可能な場合）
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間足
            period_days: 取得日数
            use_case: ユースケース
            force_source: 強制使用するソース
        
        Returns:
            tuple: (DataFrame, metadata)
                metadata: {
                    'source': str,
                    'cache_hit': bool,
                    'data_age': float (秒),
                    'fresh': bool,
                    'response_time': float (秒),
                    ...
                }
        """
        import time
        start_time = time.time()
        
        metadata = {
            'requested_at': datetime.now(pytz.UTC),
            'symbol': symbol,
            'timeframe': timeframe,
            'use_case': use_case
        }
        
        # ========================================
        # Step 1: Redisキャッシュチェック（利用可能な場合のみ）
        # ========================================
        if self.cache:
            try:
                df, cache_meta = self.cache.load_ohlcv_with_metadata(
                    symbol, timeframe, days=period_days
                )
                
                if df is not None and cache_meta:
                    # データ年齢計算
                    age = datetime.now(pytz.UTC) - cache_meta['updated_at']
                    max_age = self._get_max_age(timeframe)
                    
                    # 鮮度チェック
                    if age < max_age:
                        # ✅ 新鮮なデータ
                        metadata.update({
                            'source': 'redis',
                            'cache_hit': True,
                            'data_age': age.total_seconds(),
                            'fresh': True,
                            'response_time': time.time() - start_time,
                            'row_count': len(df)
                        })
                        
                        logger.info(
                            f"Fresh cache hit: {symbol} {timeframe} "
                            f"(age: {age.total_seconds():.0f}s < "
                            f"max: {max_age.total_seconds():.0f}s)"
                        )
                        
                        return df, metadata
                    else:
                        # ⚠️ 古いデータ
                        logger.info(
                            f"Stale cache: {symbol} {timeframe} "
                            f"(age: {age.total_seconds():.0f}s > "
                            f"max: {max_age.total_seconds():.0f}s)"
                        )
                        metadata['stale_cache_age'] = age.total_seconds()
            except Exception as e:
                logger.warning(f"Redis cache check failed (ignored): {e}")
        
        # ========================================
        # Step 2: データソースから取得
        # ========================================
        if force_source:
            sources = [force_source]
        else:
            sources = self._get_source_priority(use_case, period_days)
        
        # 利用可能なソースのみにフィルタ
        available_sources = self._filter_available_sources(sources)
        
        for source_name in available_sources:
            df = self._fetch_from_source(
                source_name, symbol, timeframe, period_days
            )
            
            if df is not None and not df.empty:
                # ========================================
                # Step 3: 取得成功 → Redisに自動保存（利用可能な場合）
                # ========================================
                if source_name != 'redis' and self.cache:
                    self._cache_result(df, symbol, timeframe)
                
                metadata.update({
                    'source': source_name,
                    'cache_hit': False,
                    'rows': len(df),
                    'fresh': True,
                    'response_time': time.time() - start_time
                })
                
                logger.info(
                    f"Data fetched from {source_name}: {symbol} {timeframe} "
                    f"({len(df)} rows, {metadata['response_time']:.2f}s)"
                )
                
                return df, metadata
        
        # ========================================
        # Step 4: 全ソース失敗
        # ========================================
        metadata.update({
            'error': 'All sources failed',
            'response_time': time.time() - start_time
        })
        
        logger.error(
            f"Failed to fetch data: {symbol} {timeframe} "
            f"(tried: {available_sources})"
        )
        
        return None, metadata
    