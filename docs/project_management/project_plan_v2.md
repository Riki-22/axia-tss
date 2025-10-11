# AXIA Phase 2 実装計画書 - 4層キャッシュ戦略とデータアクセス統合

**作成日**: 2025-10-12  
**対象期間**: Phase 2実装  
**目的**: Redis統合による4層キャッシュアーキテクチャの実装とデータアクセスの統合

---

## 📊 エグゼクティブサマリー

### Phase 2の目的
**4層キャッシュ戦略とデータアクセス統合による、パフォーマンス向上と可用性確保**

### 主要成果物
- Redis統合（24時間データ保持）
- 統合データプロバイダー（MarketDataProvider）
- S3読み取り機能の実装
- Streamlitチャート表示の最適化

### 期待される効果
- **パフォーマンス**: キャッシュヒット時90%のレイテンシ削減
- **可用性**: MT5障害時でもキャッシュデータで継続稼働
- **MT5接続競合**: キャッシュヒット率60%以上 → 競合頻度60%削減
- **コスト**: ElastiCache t4g.micro使用で月額$13

---

## 🏗️ アーキテクチャ設計

### 4層キャッシュアーキテクチャ

| 層 | 技術 | 保持期間 | TTL | レイテンシ | 用途 |
|----|------|---------|-----|-----------|------|
| **L1: Memory** | cachetools | - | - | - | Phase 3で実装 |
| **L2: Redis** | ElastiCache | 24時間 | 25時間 | ~10ms | リアルタイム取引・日中チャート |
| **L3: DynamoDB** | DynamoDB | 1年 | - | ~50ms | 取引履歴、注文状態 |
| **L4: S3** | S3 Parquet | 無期限 | - | ~200ms | ヒストリカルデータ、バックテスト |

### データアクセス戦略

```python
# 期間に基づくデータソース選択
if requested_hours <= 24:
    # Redis → MT5 → yfinance
    use_redis_first()
else:
    # S3 → yfinance (Redisスキップ)
    use_s3_first()
```

### メモリ使用量とコスト

| 項目 | 値 |
|------|-----|
| **保持データ** | 24時間分のみ |
| **推定メモリ使用量** | 35MB |
| **ElastiCacheインスタンス** | t4g.micro (0.5GB) |
| **月額費用** | $13 |

---

## 📁 ディレクトリ構造（Phase 2追加分）

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
│   │       ├── redis_client.py              # Redis接続管理
│   │       └── price_cache.py               # 価格キャッシュ（24時間保持）
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
```

---

## 🔧 実装仕様

### 1. Redis価格キャッシュ

**ファイル**: `src/infrastructure/persistence/redis/price_cache.py`

| 設定項目 | 値 | 説明 |
|---------|-----|------|
| **RETENTION_HOURS** | 24 | データ保持期間 |
| **TTL_HOURS** | 25 | RedisキーTTL（保持期間+1時間） |
| **MAX_MEMORY_MB** | 256 | メモリ上限 |
| **キーフォーマット** | `ohlcv:{symbol}:{timeframe}` | 例: ohlcv:USDJPY:H1 |

**主要メソッド**:
- `get(symbol, timeframe, hours)` - データ取得
- `set(symbol, timeframe, df)` - データ保存（24時間分のみ）
- `update(symbol, timeframe, new_data)` - データ更新
- `get_info()` - 統計情報取得

### 2. S3マーケットデータリポジトリ

**ファイル**: `src/infrastructure/persistence/s3/market_data_repository.py`

**新規メソッド**:
- `load_ohlcv(symbol, timeframe, days, start_date, end_date)` - 期間指定読み込み
- `_generate_partition_keys(symbol, timeframe, start_date, end_date)` - パーティションキー生成
- `_load_partition(prefix)` - 単一パーティション読み込み

### 3. 統合データプロバイダー

**ファイル**: `src/infrastructure/gateways/market_data/market_data_provider.py`

**データ取得メソッド**:
```python
get_data(
    symbol: str,
    timeframe: str,
    period_days: int = 1,
    use_case: str = 'trading'  # 'trading', 'chart', 'analysis'
) -> Tuple[pd.DataFrame, dict]
```

**ユースケース別優先順位**:

| use_case | 24時間以内 | 24時間超 |
|----------|-----------|----------|
| **trading** | MT5 → Redis → yfinance | MT5 → yfinance |
| **chart** | Redis → MT5 → yfinance | S3 → yfinance |
| **analysis** | Redis → S3 | S3 → yfinance |

---

## 🔄 データ収集戦略

### データ収集プロセス

| プロセス | 実行頻度 | 処理内容 | 実装ファイル |
|---------|---------|---------|------------|
| **日次データ収集** | 毎日深夜2時 | MT5から24時間分取得<br>S3保存 + Redisキャッシュ | `run_data_collector.py` |
| **Redisクリーンアップ** | 日次収集時 | 24時間超のデータ削除 | `price_cache.py` |

### cron設定

```bash
# 毎日深夜2時に日次データ収集
0 2 * * * /usr/bin/python /path/to/run_data_collector.py

# オプション: キャッシュウォームアップ
5 2 * * * /usr/bin/python /path/to/scripts/warmup_cache.py
```

---

## 📊 データフロー

### リアルタイム取引

```
Request: 直近100本のUSDJPY H1
    ↓
[MT5 Live Data] → 成功時はRedisに保存
    ↓ 失敗
[Redis Cache (24h)] → キャッシュヒット
    ↓ ミス
[yfinance API]
```

### チャート表示（30日分）

```
Request: 30日分のUSDJPY H1
    ↓
[Streamlit Cache (1h)]
    ↓ ミス
[S3 Parquet (24h超のデータ)]
    + 
[Redis Cache (直近24h)]
    ↓ 失敗
[yfinance API]
```

---

## ✅ 実装チェックリスト

### Week 1: 基盤構築

#### Day 1-2: Redis実装
- [ ] `redis_client.py` 接続管理実装
- [ ] `price_cache.py` 24時間保持ロジック実装
- [ ] TTL設定（25時間）
- [ ] メモリ監視機能
- [ ] ローカル環境での動作確認

#### Day 3: Domain層
- [ ] `market_data_repository.py` インターフェース作成
- [ ] 型定義（DataFrame, Optional等）
- [ ] docstring整備

### Week 2: データアクセス層

#### Day 4-5: S3読み取り
- [ ] `load_ohlcv()` 実装
- [ ] パーティションキー生成ロジック
- [ ] Parquetファイル読み込み
- [ ] 期間指定フィルタリング
- [ ] エラーハンドリング

#### Day 6-7: MarketDataProvider
- [ ] 基本構造実装
- [ ] ユースケース別データ取得
- [ ] フォールバック処理
- [ ] 統計情報収集
- [ ] 単体テスト作成

### Week 3: 統合

#### Day 8-9: Streamlit統合
- [ ] `chart_data_source.py` 更新
- [ ] MarketDataProvider利用
- [ ] キャッシュ設定（@st.cache_data）
- [ ] 30日分データ表示テスト
- [ ] パフォーマンス測定

#### Day 10: データ収集更新
- [ ] `run_data_collector.py` 改修
- [ ] S3保存後のRedisキャッシュ追加
- [ ] 24時間データのみ保持確認
- [ ] cron設定

### Week 4: テストと最適化

#### 統合テスト
- [ ] MT5 → Redisフォールバック
- [ ] Redis → S3フォールバック
- [ ] S3 → yfinanceフォールバック
- [ ] メモリ使用量測定（目標: 50MB以内）
- [ ] キャッシュヒット率測定（目標: 60%以上）

#### ドキュメント
- [ ] ADR-006追記
- [ ] README.md更新
- [ ] 運用手順書作成

---

## 📈 成功判定基準

### 必須要件
- [ ] Redis接続安定性: 99%以上
- [ ] メモリ使用量: 50MB以内
- [ ] S3読み取り: 5秒以内（30日分）
- [ ] チャート表示: 1秒以内
- [ ] MT5接続競合: 50%以上削減

### パフォーマンス指標

| 指標 | Phase 1 | Phase 2目標 | 判定基準 |
|------|---------|------------|---------|
| **平均レスポンス** | 100ms | 10ms | 90%削減 |
| **チャート表示** | 2-3秒 | 0.5秒 | 75%削減 |
| **Redisヒット率** | - | 60% | 60%以上 |
| **ElastiCacheコスト** | - | $13/月 | $15以内 |

---

## 🚀 Phase 3 展望

### 実装予定項目
1. **MT5 Proxyサービス** - 接続競合の完全解決
2. **L1 Memory Cache** - プロセス内キャッシュ
3. **ポジション管理機能** - Positionエンティティ追加
4. **Redis Pub/Sub** - リアルタイム通信

---
