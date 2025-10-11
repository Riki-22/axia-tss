# AXIA Phase 2 実装計画書 - 4層キャッシュ戦略とデータアクセス統合

**作成日**: 2025-10-11  
**対象期間**: Phase 2実装  
**目的**: Redis統合による4層キャッシュアーキテクチャの実装とデータアクセスの統合

---

## 📊 エグゼクティブサマリー

### Phase 2の目的
**4層キャッシュ戦略とデータアクセス統合による、パフォーマンス向上と可用性確保**

### 主要成果物
- Redis統合（用途別TTL対応）
- 統合データプロバイダー（MarketDataProvider）
- S3読み取り機能の実装
- Streamlitチャート表示の最適化

### 期待される効果
- **パフォーマンス**: キャッシュヒット時90%のレイテンシ削減
- **可用性**: MT5障害時でもキャッシュデータで継続稼働
- **MT5接続競合**: キャッシュヒット率80%以上 → 競合頻度80%削減
- **コスト**: DynamoDB読み込みリクエスト80%削減

---

## 🎯 Phase 1 → Phase 2 の変化

```
┌────────────────────────────────────────────────────────┐
│  Phase 1 (完了)          →  Phase 2 (今回)             │
├────────────────────────────────────────────────────────┤
│  MT5直接接続              →  4層キャッシュ戦略          │
│  単一データソース         →  統合データプロバイダー     │
│  S3保存のみ               →  S3読み取り対応             │
│  yfinance個別利用         →  フォールバック統合         │
└────────────────────────────────────────────────────────┘
```

---

## 🏗️ アーキテクチャ設計

### 4層キャッシュアーキテクチャ

| 層 | 技術 | TTL（用途別） | レイテンシ | 用途 |
|----|------|--------------|-----------|------|
| **L1: Memory** | cachetools | 60秒 | ~1ms | プロセス内の超高頻度アクセス |
| **L2: Redis** | ElastiCache | **用途別TTL** | ~10ms | リアルタイム・チャート・分析 |
| **L3: DynamoDB** | DynamoDB | 1年 | ~50ms | 取引履歴、注文状態（永続化） |
| **L4: S3** | S3 Parquet | 無期限 | ~200ms | ヒストリカルデータ、バックテスト |

### Redis TTL設定（用途別）

```python
CacheType.REALTIME = 300秒    # リアルタイム取引用
CacheType.CHART = 3600秒      # チャート表示用（重要！）
CacheType.DAILY = 86400秒     # 日次分析用
```

**重要な設計判断**: 
- Streamlitチャートには**1時間TTL**のCHARTキャッシュを使用
- 300秒では30日分のチャート表示に不足するため

---

## 📁 ディレクトリ構造（Phase 2完了後）

```
src/
├── domain/                                    # ドメイン層
│   ├── entities/
│   │   └── order.py                          # ✅ Phase 1完了
│   └── repositories/                         # インターフェース定義
│       ├── kill_switch_repository.py         # ✅ Phase 1完了
│       └── market_data_repository.py         # 🆕 Phase 2: 新規作成
│
├── application/                               # アプリケーション層
│   └── use_cases/
│       ├── order_processing/
│       │   └── process_sqs_order.py          # ✅ Phase 1完了
│       └── data_collection/
│           └── collect_market_data.py        # ✅ Phase 1完了（日次実行）
│
├── infrastructure/                            # インフラ層
│   ├── config/
│   │   └── settings.py                       # ✅ Phase 1完了
│   │
│   ├── persistence/
│   │   ├── dynamodb/
│   │   │   ├── order_repository.py          # ✅ Phase 1完了
│   │   │   └── kill_switch_repository.py    # ✅ Phase 1完了
│   │   │
│   │   ├── s3/
│   │   │   └── market_data_repository.py    # 🔄 Phase 2: 読み取り機能追加
│   │   │       ├── save_ohlcv_data()        # ✅ 実装済み
│   │   │       └── load_ohlcv()             # 🆕 新規実装
│   │   │
│   │   └── redis/                           # 🆕 Phase 2: 新規ディレクトリ
│   │       ├── __init__.py
│   │       ├── redis_client.py              # Redis接続管理
│   │       ├── price_cache.py               # 価格キャッシュ（用途別TTL対応）
│   │       └── cache_manager.py             # キャッシュ戦略統合
│   │
│   └── gateways/
│       ├── brokers/mt5/
│       │   ├── mt5_connection.py            # ✅ Phase 1完了
│       │   ├── mt5_order_executor.py        # ✅ Phase 1完了
│       │   ├── mt5_data_collector.py        # ✅ Phase 1完了
│       │   ├── mt5_proxy_service.py         # ⏳ Phase 3（接続競合の完全解決）
│       │   └── mt5_proxy_client.py          # ⏳ Phase 3
│       │
│       └── market_data/
│           ├── market_data_provider.py      # 🆕 Phase 2: 統合プロバイダー
│           ├── yfinance_gateway.py          # ✅ 既存実装済み
│           └── dummy_generator.py           # ✅ 既存実装済み
│
└── presentation/                              # プレゼンテーション層
    ├── cli/
    │   ├── run_order_processor.py           # ✅ Phase 1完了
    │   └── run_data_collector.py            # ✅ Phase 1完了（日次実行）
    │
    └── ui/streamlit/
        └── components/trading_charts/
            └── chart_data_source.py         # 🔄 Phase 2: MarketDataProvider利用

config/
└── base/
    └── cache.yml                            # 🆕 Phase 2: Redis設定
```

---

## 🔧 実装詳細

### 1. Domain層: インターフェース定義

**ファイル**: `src/domain/repositories/market_data_repository.py`

```python
from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional

class IMarketDataRepository(ABC):
    """市場データ取得のインターフェース"""
    
    @abstractmethod
    def get_latest_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        period: Optional[str] = None
    ) -> pd.DataFrame:
        """
        最新のOHLCVデータを取得
        
        Args:
            symbol: 通貨ペア（例: USDJPY）
            timeframe: 時間枠（例: H1）
            period: 取得期間（例: 1mo）
        
        Returns:
            pd.DataFrame: 標準OHLCV形式
        """
        pass
    
    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """最新の価格を取得"""
        pass
```

---

### 2. Infrastructure層: Redis実装

#### 2-1. Redis接続管理

**ファイル**: `src/infrastructure/persistence/redis/redis_client.py`

```python
import redis
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis接続管理"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._client = None
    
    def connect(self) -> redis.Redis:
        """Redis接続"""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            logger.info(f"Redis connected: {self.host}:{self.port}")
        return self._client
    
    def disconnect(self):
        """Redis切断"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Redis disconnected")
    
    @property
    def client(self) -> redis.Redis:
        """Redisクライアント取得"""
        if self._client is None:
            return self.connect()
        return self._client
```

#### 2-2. 価格キャッシュ（用途別TTL対応）

**ファイル**: `src/infrastructure/persistence/redis/price_cache.py`

```python
import redis
import pandas as pd
import json
import logging
from enum import Enum
from typing import Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

class CacheType(Enum):
    """キャッシュ種別"""
    REALTIME = "realtime"  # リアルタイム取引用
    CHART = "chart"        # チャート表示用
    DAILY = "daily"        # 日次分析用

class PriceCache:
    """Redis 価格キャッシュ（用途別TTL対応）"""
    
    # TTL設定（秒）
    TTL_CONFIG = {
        CacheType.REALTIME: 300,      # 5分
        CacheType.CHART: 3600,        # 1時間（重要！）
        CacheType.DAILY: 86400,       # 1日
    }
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=False
        )
        logger.info(f"PriceCache initialized: {host}:{self.port}")
    
    def _get_key(
        self,
        symbol: str,
        timeframe: str,
        cache_type: CacheType = CacheType.REALTIME
    ) -> str:
        """キー生成（用途別プレフィックス）"""
        return f"ohlcv:{cache_type.value}:{symbol}:{timeframe}"
    
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        cache_type: CacheType = CacheType.REALTIME
    ) -> Optional[pd.DataFrame]:
        """OHLCVデータ取得"""
        key = self._get_key(symbol, timeframe, cache_type)
        try:
            data = self.client.get(key)
            if data:
                df = pd.read_json(data, orient='split')
                logger.debug(f"Cache HIT [{cache_type.value}]: {key}")
                return df
            logger.debug(f"Cache MISS [{cache_type.value}]: {key}")
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def set_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        cache_type: CacheType = CacheType.REALTIME
    ) -> bool:
        """OHLCVデータ保存（用途別TTL）"""
        key = self._get_key(symbol, timeframe, cache_type)
        ttl = self.TTL_CONFIG[cache_type]
        
        try:
            json_data = df.to_json(orient='split')
            self.client.setex(key, timedelta(seconds=ttl), json_data)
            logger.debug(f"Cache SET [{cache_type.value}]: {key} (TTL={ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    def delete(
        self,
        symbol: str,
        timeframe: str,
        cache_type: CacheType = CacheType.REALTIME
    ) -> bool:
        """キャッシュ削除"""
        key = self._get_key(symbol, timeframe, cache_type)
        try:
            self.client.delete(key)
            logger.debug(f"Cache DELETE [{cache_type.value}]: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def clear_all(self) -> bool:
        """全キャッシュクリア"""
        try:
            self.client.flushdb()
            logger.info("All cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
```

#### 2-3. キャッシュマネージャー

**ファイル**: `src/infrastructure/persistence/redis/cache_manager.py`

```python
import logging
from typing import Optional, Dict
from .price_cache import PriceCache, CacheType

logger = logging.getLogger(__name__)

class CacheManager:
    """キャッシュ統合管理"""
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379):
        self.price_cache = PriceCache(host=redis_host, port=redis_port)
        self._stats: Dict[str, int] = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
    
    def get_cache_stats(self) -> Dict[str, int]:
        """キャッシュ統計取得"""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total,
            'hit_rate_percent': round(hit_rate, 2)
        }
    
    def reset_stats(self):
        """統計リセット"""
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
```

---

### 3. Infrastructure層: S3読み取り機能拡張

**ファイル**: `src/infrastructure/persistence/s3/market_data_repository.py`（拡張）

```python
from datetime import datetime, timedelta
from typing import Optional, List
import pandas as pd
import io

class S3MarketDataRepository:
    """S3マーケットデータリポジトリ（読み取り機能追加）"""
    
    def __init__(self, bucket_name: str, s3_client):
        self.bucket_name = bucket_name
        self.s3_client = s3_client
    
    def save_ohlcv_data(self, df: pd.DataFrame, symbol: str, timeframe_str: str) -> bool:
        """✅ 既に実装済み（Phase 1）"""
        # 既存実装を維持
        pass
    
    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        🆕 S3から期間指定でOHLCVデータ取得
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            days: 取得日数（start_dateが未指定の場合）
            start_date: 開始日時（任意）
            end_date: 終了日時（任意、デフォルトは現在）
        
        Returns:
            pd.DataFrame: 結合されたOHLCVデータ
        """
        # 期間計算
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=days)
        
        logger.info(f"S3からデータ取得: {symbol} {timeframe} "
                   f"({start_date.date()} ~ {end_date.date()})")
        
        # パーティションキーのリスト生成
        partition_keys = self._generate_partition_keys(
            symbol, timeframe, start_date, end_date
        )
        
        # 各パーティションからデータ取得
        dfs = []
        for key in partition_keys:
            try:
                df = self._load_partition(key)
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception as e:
                logger.warning(f"パーティション読み込み失敗: {key}, エラー: {e}")
        
        # データ結合
        if not dfs:
            logger.warning(f"S3にデータが見つかりません: {symbol} {timeframe}")
            return pd.DataFrame()
        
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df = combined_df.sort_values('timestamp_utc')
        combined_df = combined_df.drop_duplicates(subset=['timestamp_utc'])
        
        # 期間フィルタリング
        combined_df = combined_df[
            (combined_df['timestamp_utc'] >= start_date) &
            (combined_df['timestamp_utc'] <= end_date)
        ]
        
        logger.info(f"S3データ取得完了: {len(combined_df)}件")
        return combined_df
    
    def _generate_partition_keys(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """期間内の全パーティションキーを生成"""
        prefixes = []
        current_date = start_date.date()
        end = end_date.date()
        
        while current_date <= end:
            prefix = (
                f"symbol={symbol}/"
                f"timeframe={timeframe}/"
                f"source=mt5/"
                f"year={current_date.year}/"
                f"month={current_date.month:02d}/"
                f"day={current_date.day:02d}/"
            )
            prefixes.append(prefix)
            current_date += timedelta(days=1)
        
        return prefixes
    
    def _load_partition(self, prefix: str) -> Optional[pd.DataFrame]:
        """単一パーティションからデータ読み込み"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return None
            
            dfs = []
            for obj in response['Contents']:
                key = obj['Key']
                if not key.endswith('.parquet'):
                    continue
                
                obj_data = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                df = pd.read_parquet(io.BytesIO(obj_data['Body'].read()))
                dfs.append(df)
            
            if not dfs:
                return None
            
            return pd.concat(dfs, ignore_index=True)
            
        except Exception as e:
            logger.error(f"パーティション読み込みエラー: {prefix}, {e}")
            return None
```

---

### 4. Infrastructure層: 統合データプロバイダー

**ファイル**: `src/infrastructure/gateways/market_data/market_data_provider.py`

```python
import pandas as pd
import logging
from typing import Optional

from src.domain.repositories.market_data_repository import IMarketDataRepository
from src.infrastructure.persistence.redis.price_cache import PriceCache, CacheType
from src.infrastructure.persistence.s3.market_data_repository import S3MarketDataRepository
from src.infrastructure.gateways.brokers.mt5.mt5_data_collector import MT5DataCollector
from src.infrastructure.gateways.market_data.yfinance_gateway import YFinanceGateway
from src.infrastructure.gateways.market_data.dummy_generator import DummyMarketDataGenerator

logger = logging.getLogger(__name__)

class MarketDataProvider(IMarketDataRepository):
    """市場データの統合プロバイダー（4層フォールバック戦略）"""
    
    def __init__(
        self,
        use_redis: bool = False,
        use_s3: bool = False,
        use_mt5: bool = True,
        use_yfinance: bool = True
    ):
        # Redis キャッシュ（Phase 2）
        self.cache = PriceCache() if use_redis else None
        
        # S3リポジトリ
        self.s3_repository = S3MarketDataRepository(...) if use_s3 else None
        
        # データソース
        self.mt5 = MT5DataCollector() if use_mt5 else None
        self.yfinance = YFinanceGateway() if use_yfinance else None
        self.dummy = DummyMarketDataGenerator(seed=42)
        
        logger.info(f"MarketDataProvider initialized: "
                   f"Redis={use_redis}, S3={use_s3}, MT5={use_mt5}, YF={use_yfinance}")
    
    def get_ohlcv_for_trading(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        リアルタイム取引用データ取得（短期TTL）
        
        優先順位:
        1. Redis (realtime, TTL: 300秒)
        2. MT5 リアルタイム
        3. フォールバック
        """
        # Level 1: Redis キャッシュ（realtime）
        if self.cache:
            cached = self.cache.get_ohlcv(
                symbol, timeframe,
                cache_type=CacheType.REALTIME
            )
            if cached is not None and len(cached) >= count:
                logger.info(f"✅ Trading data from Redis: {symbol} {timeframe}")
                return cached.tail(count)
        
        # Level 2: MT5リアルタイム
        if self.mt5 and self.mt5.is_connected():
            try:
                df = self.mt5.get_rates(symbol, timeframe, count)
                if not df.empty:
                    logger.info(f"✅ Trading data from MT5: {symbol} {timeframe}")
                    
                    # Redisにキャッシュ（realtime）
                    if self.cache:
                        self.cache.set_ohlcv(
                            symbol, timeframe, df,
                            cache_type=CacheType.REALTIME
                        )
                    return df
            except Exception as e:
                logger.warning(f"MT5 data fetch failed: {e}")
        
        # Level 3: フォールバック
        return self._fallback_data_source(symbol, timeframe, count)
    
    def get_ohlcv_for_chart(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> pd.DataFrame:
        """
        チャート表示用データ取得（長期TTL）
        
        優先順位:
        1. Redis (chart, TTL: 3600秒)
        2. S3 (Parquet)
        3. yfinance
        4. dummy_generator
        """
        # Level 1: Redis キャッシュ（chart）
        if self.cache:
            cached = self.cache.get_ohlcv(
                symbol, timeframe,
                cache_type=CacheType.CHART
            )
            if cached is not None and not cached.empty:
                required_bars = self._calculate_required_bars(days, timeframe)
                if len(cached) >= required_bars:
                    logger.info(f"✅ Chart data from Redis: {symbol} {timeframe}")
                    return cached
        
        # Level 2: S3から取得
        if self.s3_repository:
            try:
                df = self.s3_repository.load_ohlcv(symbol, timeframe, days)
                if not df.empty:
                    logger.info(f"✅ Chart data from S3: {symbol} {timeframe}")
                    
                    # Redisにキャッシュ（chart）
                    if self.cache:
                        self.cache.set_ohlcv(
                            symbol, timeframe, df,
                            cache_type=CacheType.CHART
                        )
                    return df
            except Exception as e:
                logger.warning(f"S3 data fetch failed: {e}")
        
        # Level 3: yfinanceフォールバック
        if self.yfinance:
            try:
                period = self._get_yfinance_period(days)
                df = self.yfinance.fetch_ohlcv(symbol, timeframe, period)
                if not df.empty:
                    logger.info(f"⚠️ Chart data from yfinance: {symbol} {timeframe}")
                    
                    # Redisにキャッシュ（chart）
                    if self.cache:
                        self.cache.set_ohlcv(
                            symbol, timeframe, df,
                            cache_type=CacheType.CHART
                        )
                    return df
            except Exception as e:
                logger.warning(f"yfinance fetch failed: {e}")
        
        # Level 4: 最終手段（dummy data）
        logger.warning(f"🔴 Using dummy data for chart: {symbol} {timeframe}")
        return self.dummy.generate_ohlcv(days, timeframe)
    
    def get_latest_price(self, symbol: str) -> float:
        """最新価格を取得（簡易版）"""
        df = self.get_ohlcv_for_trading(symbol, 'M1', count=1)
        if not df.empty:
            return float(df.iloc[-1]['close'])
        return 0.0
    
    def _calculate_required_bars(self, days: int, timeframe: str) -> int:
        """必要な足数を計算"""
        bars_per_day = {
            'M1': 1440, 'M5': 288, 'M15': 96, 'M30': 48,
            'H1': 24, 'H4': 6, 'D1': 1
        }
        return days * bars_per_day.get(timeframe, 24)
    
    def _get_yfinance_period(self, days: int) -> str:
        """日数をyfinanceの期間文字列に変換"""
        if days <= 7:
            return '7d'
        elif days <= 30:
            return '1mo'
        elif days <= 90:
            return '3mo'
        elif days <= 180:
            return '6mo'
        else:
            return '1y'
    
    def _fallback_data_source(
        self,
        symbol: str,
        timeframe: str,
        count: int
    ) -> pd.DataFrame:
        """フォールバックデータソース"""
        # yfinance試行
        if self.yfinance:
            try:
                df = self.yfinance.fetch_ohlcv(symbol, timeframe, period='1mo')
                if not df.empty:
                    return df.tail(count)
            except:
                pass
        
        # 最終手段: dummy data
        return self.dummy.generate_ohlcv(days=7, timeframe=timeframe).tail(count)
```

---

### 5. Presentation層: Streamlit更新

**ファイル**: `src/presentation/ui/streamlit/components/trading_charts/chart_data_source.py`（変更）

```python
import streamlit as st
import pandas as pd
import logging

from src.infrastructure.gateways.market_data.market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)

class ChartDataSource:
    """チャートデータ取得（MarketDataProvider経由）"""
    
    def __init__(self):
        # MarketDataProvider を利用
        self.provider = MarketDataProvider(
            use_redis=True,   # 🆕 Redis有効化
            use_s3=True,      # 🆕 S3読み取り有効化
            use_mt5=False,    # チャート表示にはMT5不要
            use_yfinance=True
        )
    
    @st.cache_data(ttl=3600)  # Streamlit側でも1時間キャッシュ
    def fetch_market_data(
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> pd.DataFrame:
        """
        チャート用データ取得
        
        データフロー:
        1. Streamlit cache (1時間)
        2. Redis chart cache (1時間)
        3. S3 Parquet
        4. yfinance
        5. dummy_generator
        """
        provider = MarketDataProvider(
            use_redis=True,
            use_s3=True,
            use_mt5=False,
            use_yfinance=True
        )
        
        return provider.get_ohlcv_for_chart(symbol, timeframe, days)
    
    def get_data_source_info(self) -> str:
        """データソース情報を取得"""
        return "Integrated Provider (Redis/S3/yfinance)"
```

---

## 📊 データフロー図

### リアルタイム取引の場合

```
Request: 直近100本のUSDJPY H1
    ↓
┌─────────────────────────────────┐
│ L1: Memory (TTL: 60秒)          │
│ (Phase 2では未実装)              │
└─────────────────────────────────┘
    ↓ miss
┌─────────────────────────────────┐
│ L2: Redis realtime (TTL: 300秒) │
│ Key: ohlcv:realtime:USDJPY:H1   │
└─────────────────────────────────┘
    ↓ miss
┌─────────────────────────────────┐
│ MT5 Live Data                   │
└─────────────────────────────────┘
```

### Streamlitチャート表示の場合

```
Request: 30日分のUSDJPY H1
    ↓
┌─────────────────────────────────┐
│ Streamlit Cache (ttl: 3600秒)   │
└─────────────────────────────────┘
    ↓ miss
┌─────────────────────────────────┐
│ L2: Redis chart (TTL: 3600秒)   │ ← 重要！
│ Key: ohlcv:chart:USDJPY:H1      │
└─────────────────────────────────┘
    ↓ miss
┌─────────────────────────────────┐
│ L4: S3 Parquet                  │
│ (期間指定読み取り)               │
└─────────────────────────────────┘
    ↓ なし
┌─────────────────────────────────┐
│ yfinance API                    │
└─────────────────────────────────┘
    ↓ 失敗
┌─────────────────────────────────┐
│ dummy_generator                 │
└─────────────────────────────────┘
```

---

## 🔄 データ収集戦略

### 2つのデータ収集プロセス

| プロセス | 実行頻度 | 取得期間 | 保存先 | 用途 | 実装状況 |
|---------|---------|---------|--------|------|---------|
| **長期データ収集**<br>(data_collector) | **日次（深夜2時）** | 過去90日 | S3 Parquet<br>+ Redis chart | チャート表示<br>バックテスト | ✅ Phase 1完了<br>🔄 Redis追加 |
| リアルタイム収集<br>(order_manager統合) | 常時稼働<br>（5分毎） | 直近100本 | Redis realtime | 取引判断 | ⏳ Phase 3 |

### cron設定

```bash
# 毎日深夜2時に長期データ収集
0 2 * * * /usr/bin/python /path/to/run_data_collector.py

# Redisキャッシュのウォームアップも同時実行
5 2 * * * /usr/bin/python /path/to/scripts/warmup_cache.py
```

**推奨**: 既存data_collectorは**日次実行のまま**でOK

---

## 🚫 MT5 Proxy について（Phase 3へ延期）

### 現状の位置づけ

```
Phase 2（今回実装）:
  ✅ Redis統合
  ✅ MarketDataProvider
  ✅ S3読み取り機能

Phase 3（次フェーズ）:
  ⏳ MT5 Proxyサービス
  ⏳ Redis Pub/Sub通信
  ⏳ 接続競合の完全解決
```

**理由**:
- Phase 2のRedis統合で**競合頻度80%削減**（キャッシュヒット時はMT5接続不要）
- MT5 Proxyは複雑性が高く、ROIが段階的
- 完全解決はPhase 3で実施

---

## ✅ Phase 2 実装チェックリスト

### Week 1: Redis基盤構築

#### Day 1-2: Redis実装
- [ ] `redis_client.py` 接続管理実装
- [ ] `price_cache.py` 用途別TTL対応実装
- [ ] `cache_manager.py` 統合管理実装
- [ ] Redis接続テスト
- [ ] ローカル環境でのRedis動作確認

#### Day 3: Domain層インターフェース
- [ ] `market_data_repository.py` インターフェース作成
- [ ] 型定義の明確化
- [ ] ドキュメント整備

### Week 2: データプロバイダーとS3拡張

#### Day 4-5: S3読み取り機能
- [ ] `S3MarketDataRepository.load_ohlcv()` 実装
- [ ] `_generate_partition_keys()` 実装
- [ ] `_load_partition()` 実装
- [ ] S3読み取りテスト（期間指定）

#### Day 6-7: MarketDataProvider実装
- [ ] `market_data_provider.py` 基本実装
- [ ] `get_ohlcv_for_trading()` 実装
- [ ] `get_ohlcv_for_chart()` 実装
- [ ] フォールバック処理実装
- [ ] 統合テスト

### Week 3: 統合とUI更新

#### Day 8-9: Streamlit統合
- [ ] `chart_data_source.py` MarketDataProvider利用に変更
- [ ] Streamlitキャッシュ設定
- [ ] チャート表示テスト（30日分データ）
- [ ] パフォーマンス測定

#### Day 10: data_collector更新
- [ ] Redisキャッシュ書き込み追加
- [ ] S3保存後にRedisキャッシュ
- [ ] 日次実行テスト

### 最終週: テストとドキュメント

#### 統合テスト
- [ ] Redis → MT5フォールバックテスト
- [ ] Redis → S3フォールバックテスト
- [ ] S3 → yfinanceフォールバックテスト
- [ ] キャッシュヒット率測定
- [ ] レスポンスタイム測定

#### ドキュメント
- [ ] ADR-006追記
- [ ] README.md更新
- [ ] API仕様書更新
- [ ] 運用手順書更新

---

## 📈 期待される効果

### パフォーマンス向上

| 指標 | Phase 1 | Phase 2（目標） | 改善率 |
|------|---------|----------------|--------|
| **平均レスポンス** | 100ms | 10ms | 90%削減 |
| **チャート表示** | 2-3秒 | 0.5秒 | 75%削減 |
| **MT5接続競合** | 高頻度 | 低頻度 | 80%削減 |

### コスト削減

| 項目 | Phase 1 | Phase 2（目標） | 削減率 |
|------|---------|----------------|--------|
| **DynamoDB読み込み** | 1000回/日 | 200回/日 | 80%削減 |
| **MT5 API呼び出し** | 500回/日 | 100回/日 | 80%削減 |

---

## 🎯 成功判定基準

### 必須要件
- [ ] Redis接続が安定稼働（99%以上の可用性）
- [ ] S3から30日分のデータを5秒以内に取得
- [ ] Streamlitチャート表示が1秒以内
- [ ] MT5接続競合エラーが80%削減

### 推奨要件
- [ ] キャッシュヒット率80%以上
- [ ] 平均レスポンスタイム10ms以下
- [ ] Redisメモリ使用量256MB以内
- [ ] エラー率0.1%以下

---

## 📝 次のステップ（Phase 3）

### Phase 3での実装予定
1. **MT5 Proxyサービス**
   - Redis Pub/Sub経由の通信
   - 接続競合の完全解決
   - マルチプロセス対応

2. **L1 Memory Cache実装**
   - cachetools導入
   - プロセス内超高速キャッシュ

3. **ポジション管理機能**
   - Positionエンティティ追加
   - ポジショントラッキング

---

## 📞 連絡先・サポート

**プロジェクト**: AXIA Trading System  
**Phase**: Phase 2 - 4層キャッシュ戦略実装  
**ドキュメント**: `docs/project_plan.md`  
**ADR参照**: `docs/architecture_dicision_records.md` (ADR-006)

---

**最終更新**: 2025-10-11  
**次回レビュー**: Phase 2完了時