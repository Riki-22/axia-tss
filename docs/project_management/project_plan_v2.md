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
- 統合データプロバイダー（OhlcvDataProvider）
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
│       └── ohlcv_data_repository.py         # 🆕 Phase 2: 新規作成
│
├── application/                               # アプリケーション層
│   └── use_cases/
│       ├── order_processing/
│       │   └── process_sqs_order.py          # ✅ Phase 1完了
│       └── data_collection/
│           └── collect_ohlcv_data.py        # ✅ Phase 1完了（日次実行）
│
├── infrastructure/                            # インフラ層
│   ├── config/
│   │   └── settings.py                       # ✅ Phase 1完了
│   │
│   ├── persistence/
│   │   ├── dynamodb/
│   │   │   ├── dynamodb_order_repository.py          # ✅ Phase 1完了
│   │   │   └── dynamodb_kill_switch_repository.py    # ✅ Phase 1完了
│   │   │
│   │   ├── s3/
│   │   │   └── ohlcv_data_repository.py    # 🔄 Phase 2: 読み取り機能追加
│   │   │       ├── save_ohlcv_data()        # ✅ 実装済み
│   │   │       └── load_ohlcv()             # 🆕 新規実装
│   │   │
│   │   └── redis/                           # 🆕 Phase 2: 新規ディレクトリ
│   │       ├── redis_client.py              # Redis接続管理
│   │       └── redis_ohlcv_data_repository.py               # 価格キャッシュ（24時間保持）
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
│           ├── ohlcv_data_provider.py      # 🆕 Phase 2: 統合プロバイダー
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
            └── chart_data_source.py         # 🔄 Phase 2: OhlcvDataProvider利用
```

---

## 🔧 実装仕様

### 1. Redis価格キャッシュ

**ファイル**: `src/infrastructure/persistence/redis/redis_ohlcv_data_repository.py`

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

**ファイル**: `src/infrastructure/persistence/s3/s3_ohlcv_data_repository.py`

**新規メソッド**:
- `load_ohlcv(symbol, timeframe, days, start_date, end_date)` - 期間指定読み込み
- `_generate_partition_keys(symbol, timeframe, start_date, end_date)` - パーティションキー生成
- `_load_partition(prefix)` - 単一パーティション読み込み

### 3. 統合データプロバイダー

**ファイル**: `src/infrastructure/gateways/market_data/ohlcv_data_provider.py`

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
| **Redisクリーンアップ** | 日次収集時 | 24時間超のデータ削除 | `redis_ohlcv_data_repository.py` |

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
- [ ] `redis_ohlcv_data_repository.py` 24時間保持ロジック実装
- [ ] TTL設定（25時間）
- [ ] メモリ監視機能
- [ ] ローカル環境での動作確認

#### Day 3: Domain層
- [ ] `ohlcv_data_repository.py` インターフェース作成
- [ ] 型定義（DataFrame, Optional等）
- [ ] docstring整備

### Week 2: データアクセス層

#### Day 4-5: S3読み取り
- [ ] `load_ohlcv()` 実装
- [ ] パーティションキー生成ロジック
- [ ] Parquetファイル読み込み
- [ ] 期間指定フィルタリング
- [ ] エラーハンドリング

#### Day 6-7: OhlcvDataProvider
- [ ] 基本構造実装
- [ ] ユースケース別データ取得
- [ ] フォールバック処理
- [ ] 統計情報収集
- [ ] 単体テスト作成

### Week 3: 統合

#### Day 8-9: Streamlit統合
- [ ] `chart_data_source.py` 更新
- [ ] OhlcvDataProvider利用
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

---

# 📊 Week 2 完了状況レポート

**完了日**: 2025年10月16日  
**Phase**: Phase 2 - Redis統合 & データアクセス層実装 + Phase 1実地検証完了  
**進捗**: Week 2完了 + 実運用検証完了 (100%)

---

## ✅ 実装完了サマリー

### Week 2の成果 + ボーナス達成

```
Week 2: データアクセス層実装 + アーキテクチャ改善 + 実運用検証

Day 1 ████████████████████ 100% ✅ S3パーティション読み込み
Day 2 ████████████████████ 100% ✅ メイン読み込み + Redis統合
Day 3 ████████████████████ 100% ✅ Provider基本構造
Day 4 ████████████████████ 100% ✅ Provider完成
Day 5 ████████████████████ 100% ✅ 統合テスト・最適化
追加1 ████████████████████ 100% ✅ 命名規則統一・アーキテクチャ改善
追加2 ████████████████████ 100% ✅ Data Collector実地検証完了🎉

Week 2進捗: 100% 完了 + 2つのボーナス達成！
```

---

## 🎯 実装完了機能

### 1. **統合データアクセス層（OhlcvDataProvider）**

```python
実装済み機能:
✅ 複数データソースの透過的な統合（Redis/MT5/S3/yfinance）
✅ ユースケース別最適化（trading/chart/analysis）
✅ 自動フォールバック戦略
✅ 自動Redisキャッシュ
✅ 統計情報収集
✅ 詳細なメタデータ返却

```

### 2. **リポジトリ層の完成**

```
Domain層（インターフェース）:
✅ IOhlcvDataRepository - OHLCV データの抽象定義
✅ IKillSwitchRepository - Kill Switch の抽象定義
✅ IOrderRepository - 注文の抽象定義

Infrastructure層（実装）:
✅ RedisOhlcvDataRepository - 24時間ホットキャッシュ
✅ S3OhlcvDataRepository - 長期コールドストレージ
✅ DynamoDBKillSwitchRepository - Kill Switch 永続化
✅ DynamoDBOrderRepository - 注文履歴永続化
```

### 3. **アーキテクチャ改善**

```
命名規則の統一:
✅ ファイル名: {技術}_{ドメイン}_repository.py
✅ クラス名: {技術}{ドメイン}Repository

改善効果:
✅ 一貫性: 全リポジトリで統一された命名
✅ 検索性: 技術スタック + ドメインで一発検索
✅ 明確性: market_data → ohlcv_data で具体化
✅ 拡張性: 新規リポジトリの命名が明確

クリーンアーキテクチャ準拠:
✅ Infrastructure層がDomain層のインターフェースに依存
✅ 依存関係逆転の原則（DIP）実現
✅ テスタビリティ向上
```

### 4. **🎉 Data Collector実地検証完了（NEW！）**

```
実運用での動作確認:
✅ MT5接続: 正常動作
✅ データ取得: 45タスク 100%成功
✅ S3保存: 全通貨ペア・全タイムフレーム保存成功
✅ Redis保存: 46キー（8.84 MB）保存成功
✅ Redis シリアライズ問題: 完全解決

収集データ:
✅ 通貨ペア: USDJPY, EURUSD, EURJPY, GBPUSD, GBPJPY (5ペア)
✅ タイムフレーム: M1, M5, M15, M30, H1, H4, D1, W1, MN1 (9種類)
✅ 総データセット: 45 (5ペア × 9タイムフレーム)
✅ データ品質: 100%（エラーなし）

Redis統計:
✅ キー数: 46（データ45 + メタデータ）
✅ メモリ使用量: 8.84 MB / 50 MB（17.7%）
✅ メモリステータス: OK
✅ TTL管理: NYクローズ基準（71,655秒 ≈ 19.9時間）
```

### 5. **Redis シリアライズ問題の解決（NEW！）**

```python
問題:
❌ pandas Timestamp オブジェクトが msgpack でシリアライズ不可
❌ DatetimeIndex の保存・復元ができない
❌ データ型情報の喪失

解決策:
✅ Timestamp → ISO文字列への変換実装
✅ DatetimeIndex の保存・復元機能実装
✅ インデックス情報のメタデータ化
✅ データ型の完全復元

実装内容:
# _serialize_dataframe
├─ インデックス情報の保存 (index_name, is_datetime_index)
├─ 全datetime型カラムの自動変換
├─ records形式での辞書化
└─ msgpack シリアライズ

# _deserialize_dataframe  
├─ datetime型カラムの自動復元
├─ DatetimeIndex の完全復元
├─ データ型の正確な復元
└─ タイムゾーン情報の保持

結果:
✅ 全73テスト合格
✅ 実運用で100%動作
✅ データ完全性保証
```

---

## 📁 最終ディレクトリ構造（確定版）

### Domain層（ビジネスルール）

```
src/domain/
├── entities/
│   └── order.py
├── repositories/                           # インターフェース
│   ├── ohlcv_data_repository.py           ✅ リネーム完了
│   │   └── IOhlcvDataRepository
│   ├── kill_switch_repository.py
│   │   └── IKillSwitchRepository
│   └── order_repository.py
│       └── IOrderRepository
└── services/
    ├── order_validation.py
    └── technical_indicators/               ⏳ Phase 3で実装予定
```

### Infrastructure層（技術実装）

```
src/infrastructure/
├── persistence/
│   ├── redis/
│   │   ├── redis_client.py                ✅ 接続管理（実運用検証済み）
│   │   └── redis_ohlcv_data_repository.py ✅ シリアライズ問題解決済み
│   │       └── RedisOhlcvDataRepository
│   │
│   ├── s3/
│   │   └── s3_ohlcv_data_repository.py    ✅ パーティション保存検証済み
│   │       └── S3OhlcvDataRepository
│   │
│   └── dynamodb/
│       ├── base_repository.py
│       ├── dynamodb_kill_switch_repository.py ✅ リネーム完了
│       │   └── DynamoDBKillSwitchRepository
│       └── dynamodb_order_repository.py    ✅ リネーム完了
│           └── DynamoDBOrderRepository
│
└── gateways/
    ├── brokers/
    │   └── mt5/
    │       ├── mt5_connection.py          ✅ 実運用検証済み
    │       └── mt5_data_collector.py      ✅ 45タスク成功
    │
    └── market_data/
        └── ohlcv_data_provider.py          ✅ リネーム完了
            └── OhlcvDataProvider
```

### Application層（ユースケース）

```
src/application/
└── use_cases/
    ├── data_collection/
    │   └── collect_ohlcv_data.py           ✅ 実運用検証済み
    │       └── CollectOhlcvDataUseCase     ✅ 100%成功率
    ├── feature_engineering/                ⏳ Phase 3で実装予定
    └── order_processing/
        └── process_sqs_order.py
            └── ProcessSqsOrderUseCase
```

### Test層

```
tests/
├── unit/
│   ├── application/
│   │   └── use_cases/
│   │       └── data_collection/
│   │           └── test_collect_ohlcv_data.py     ✅ 7テスト合格
│   │
│   └── infrastructure/
│       ├── gateways/
│       │   └── market_data/
│       │       └── test_ohlcv_data_provider.py    ✅ 20テスト合格
│       │
│       └── persistence/
│           ├── redis/
│           │   ├── test_redis_client.py           ✅ 13テスト合格
│           │   └── test_redis_ohlcv_data_repository.py ✅ 15テスト合格
│           └── s3/
│               └── test_s3_ohlcv_data_repository.py    ✅ 18テスト合格
│
└── integration/
    └── test_data_collection_e2e.py         ⏳ 次週実装予定
```

---

## 📊 実装統計（最終版）

### コード規模

| カテゴリ | 行数 | ファイル数 |
|---------|------|----------|
| **Production Code** | ~4,200行 | 13ファイル |
| **Test Code** | ~1,800行 | 8ファイル |
| **Scripts** | ~600行 | 2ファイル |
| **合計** | **~6,600行** | **23ファイル** |

### テストカバレッジ

| カテゴリ | テスト数 | 成功率 |
|---------|---------|--------|
| **Domain層** | 0 | - |
| **Application層** | 7 | 100% ✅ |
| **Infrastructure - Redis** | 28 | 100% ✅ |
| **Infrastructure - S3** | 18 | 100% ✅ |
| **Infrastructure - Provider** | 20 | 100% ✅ |
| **合計** | **73** | **100%** ✅ |

### 実運用データ

| 項目 | 値 |
|------|-----|
| **データ収集タスク** | 45 |
| **成功率** | 100% ✅ |
| **通貨ペア** | 5 |
| **タイムフレーム** | 9 |
| **Redis キー数** | 46 |
| **メモリ使用量** | 8.84 MB |
| **S3保存件数** | 45 |
| **エラー件数** | 0 |

---

## 🎉 Phase進捗状況

### Phase 1: データ取得・保存層（完了✅）

```
Phase 1: データ収集基盤構築

Week 1 ████████████████████ 100% ✅ MT5接続・データ取得実装
Week 2 ████████████████████ 100% ✅ S3保存機能実装
Week 3 ████████████████████ 100% ✅ Data Collector統合
Week 4 ████████████████████ 100% ✅ 実地検証・デバッグ

Phase 1進捗: ████████████████████ 100% 完了！

実運用検証:
✅ MT5接続: 正常動作
✅ データ取得: 45タスク 100%成功
✅ S3保存: 全データ保存成功
✅ Redis保存: シリアライズ問題解決済み
✅ データ品質: 100%
```

### Phase 2: データ提供層（95%完了）

```
Phase 2: Redis統合 & データアクセス層実装

Week 1 ████████████████████ 100% ✅ Redis基盤実装
       - RedisClient実装
       - RedisOhlcvDataRepository実装
       - NYクローズ基準TTL実装
       - メモリ監視機能

Week 2 ████████████████████ 100% ✅ データアクセス層実装
       - S3OhlcvDataRepository実装（読み取り機能）
       - OhlcvDataProvider実装（統合プロバイダー）
       - フォールバック戦略実装
       - 自動キャッシュ機能
       - 統計情報収集
       - 命名規則統一（アーキテクチャ改善）
       - Redis シリアライズ問題解決
       - Data Collector実地検証完了

```
