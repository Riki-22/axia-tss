# src/infrastructure/gateways/market_data/market_data_provider.py
"""統合マーケットデータプロバイダー"""

import logging
import time
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
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
        - ユースケース別の最適なデータソース選択
        - フォールバック戦略の実行
        - Redisへの自動キャッシュ管理
        - 統計情報の収集
        - エラーハンドリング
    
    データソース:
        - Redis (PriceCacheRepository): 24時間キャッシュ
        - MT5 (MT5DataCollector): リアルタイムデータ
        - S3 (S3MarketDataRepository): 過去データ
        - yfinance: フォールバック用API
    
    ユースケース:
        - trading: リアルタイム取引用（低レイテンシ優先）
        - chart: チャート表示用（中レイテンシ許容）
        - analysis: 分析・バックテスト用（大量データ）
    
    Example:
        provider = MarketDataProvider(
            price_cache=cache,
            mt5_data_collector=mt5,
            s3_repository=s3_repo
        )
        
        # リアルタイム取引用（24時間）
        df, meta = provider.get_data('USDJPY', 'H1', 1, 'trading')
        
        # チャート表示用（30日）
        df, meta = provider.get_data('USDJPY', 'H1', 30, 'chart')
    """
    
    def __init__(
        self,
        price_cache: PriceCacheRepository,
        mt5_data_collector: Optional[MT5DataCollector] = None,
        s3_repository: Optional[S3MarketDataRepository] = None,
        yfinance_client: Optional[Any] = None
    ):
        """
        Args:
            price_cache: Redisキャッシュリポジトリ（必須）
            mt5_data_collector: MT5データ収集器（オプション）
            s3_repository: S3リポジトリ（オプション）
            yfinance_client: yfinanceクライアント（オプション）
        
        Note:
            オプショナルなソースがNoneの場合、
            そのソースへのアクセスはスキップされる
        """
        self.cache = price_cache
        self.mt5 = mt5_data_collector
        self.s3 = s3_repository
        self.yfinance = yfinance_client
        
        # 統計情報
        self._stats = {
            'total_requests': 0,
            'source_usage': defaultdict(int),
            'response_times': defaultdict(list),
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # 利用可能なソースをログ出力
        available_sources = []
        if self.cache:
            available_sources.append('redis')
        if self.mt5:
            available_sources.append('mt5')
        if self.s3:
            available_sources.append('s3')
        if self.yfinance:
            available_sources.append('yfinance')
        
        logger.info(
            f"MarketDataProvider initialized with sources: {available_sources}"
        )
    
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
        
        # ユースケース別の優先順位
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
    
    # ========================================
    # 統計情報
    # ========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        統計情報を取得
        
        Returns:
            Dict: 統計情報
                - total_requests: 総リクエスト数
                - source_usage: ソース別使用回数
                - avg_response_time: ソース別平均レスポンス時間
                - cache_hit_rate: キャッシュヒット率
        
        Example:
            stats = provider.get_stats()
            print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
        """
        total = self._stats['total_requests']
        
        # 平均レスポンス時間を計算
        avg_response_time = {}
        for source, times in self._stats['response_times'].items():
            if times:
                avg_response_time[source] = sum(times) / len(times)
            else:
                avg_response_time[source] = 0.0
        
        # キャッシュヒット率
        cache_hit_rate = 0.0
        if total > 0:
            cache_hit_rate = self._stats['cache_hits'] / total
        
        return {
            'total_requests': total,
            'source_usage': dict(self._stats['source_usage']),
            'avg_response_time': avg_response_time,
            'cache_hit_rate': cache_hit_rate,
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses']
        }
    
    def reset_stats(self):
        """統計情報をリセット"""
        self._stats = {
            'total_requests': 0,
            'source_usage': defaultdict(int),
            'response_times': defaultdict(list),
            'cache_hits': 0,
            'cache_misses': 0
        }
        logger.info("Statistics reset")


# 動作確認スクリプト
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # プロジェクトルートをパスに追加
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    from src.infrastructure.di.container import container
    
    # ロギング設定
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
    )
    
    # PriceCache取得
    price_cache = container.get_price_cache()
    
    # MarketDataProvider作成
    provider = MarketDataProvider(
        price_cache=price_cache,
        mt5_data_collector=None,  # テストのためNone
        s3_repository=None,
        yfinance_client=None
    )
    
    # ソース優先順位テスト
    print("\n" + "=" * 60)
    print("Source Priority Test")
    print("=" * 60)
    
    test_cases = [
        ('trading', 1, None),
        ('trading', 30, None),
        ('chart', 1, None),
        ('chart', 30, None),
        ('analysis', 1, None),
        ('analysis', 90, None),
        ('trading', 1, 's3'),  # force_source
    ]
    
    for use_case, days, force in test_cases:
        priority = provider._get_source_priority(use_case, days, force)
        print(f"\n{use_case:10s} {days:3d}d (force={force}): {priority}")
    
    # 統計情報テスト
    print("\n" + "=" * 60)
    print("Statistics")
    print("=" * 60)
    stats = provider.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")