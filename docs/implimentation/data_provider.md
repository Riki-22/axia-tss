# Week 2: データアクセス層実装計画書

**作成日**: 2025年10月15日  
**対象期間**: Week 2 (Day 1-5)  
**目的**: 統合データプロバイダーによる透過的なデータアクセスの実現

---

## 📊 エグゼクティブサマリー

### Week 2の目的

**複数のデータソースを統合し、ユースケースに応じた最適なデータアクセスを実現**

### 主要成果物

- **S3読み取り機能**: 過去データの効率的な読み込み
- **MarketDataProvider**: 統合データアクセスインターフェース
- **フォールバック戦略**: 高可用性の実現
- **統計情報収集**: データソース使用状況の可視化

### 期待される効果

- **MT5接続競合**: キャッシュヒット率60%以上で競合60%削減
- **レスポンス時間**: キャッシュヒット時90%改善（100ms → 10ms）
- **可用性向上**: MT5障害時もS3/yfinanceで継続稼働
- **開発効率**: データアクセスロジックの一元化

---

## 🎯 現状と課題

### 現状の問題点

```
各コンポーネントが個別にデータソースにアクセス
  ├─ Streamlit → MT5直接アクセス
  ├─ data_collector → MT5 + S3保存
  └─ バックテスト → S3読み込み（未実装）

問題:
  ✗ MT5接続競合が発生
  ✗ Redisキャッシュが活用されない
  ✗ フォールバック機能なし
  ✗ データソース切り替えが困難
  ✗ エラーハンドリングが分散
```

### Week 2で実現する姿

```
┌─────────────────────────────────────────┐
│ Application Layer (統一インターフェース) │
│  ├─ Streamlit Dashboard                 │
│  ├─ Backtesting Engine                  │
│  └─ Trading Strategy                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ MarketDataProvider ★Week 2実装★        │
│  ├─ ユースケース判定                     │
│  ├─ データソース自動選択                 │
│  ├─ フォールバック制御                   │
│  └─ 統計情報収集                         │
└────────────────┬────────────────────────┘
                 │
       ┌─────────┼─────────┬─────────┐
       ▼         ▼         ▼         ▼
   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
   │Redis │ │ MT5  │ │ S3   │ │yfinance  │
   │Cache │ │Live  │ │Store │ │API       │
   └──────┘ └──────┘ └──────┘ └──────────┘
   Week1✅  既存✅   Week2★  既存✅

解決:
  ✓ 自動的に最適なソースを選択
  ✓ フォールバック機能で高可用性
  ✓ Redisキャッシュの透過的な活用
  ✓ 一元化されたエラーハンドリング
```

---

## 🏗️ アーキテクチャ設計

### データソース優先順位マトリックス

| ユースケース | 24時間以内 | 24時間超 |
|------------|-----------|---------|
| **trading**<br>(リアルタイム取引) | MT5 → Redis<br>→ yfinance | MT5 → yfinance |
| **chart**<br>(チャート表示) | Redis → MT5<br>→ yfinance | Redis → S3<br>→ yfinance |
| **analysis**<br>(分析・バックテスト) | Redis → S3<br>→ yfinance | S3 → Redis<br>→ yfinance |

### フォールバック戦略（例: chart, 30日分）

```
Request: 30日分のUSDJPY H1データ

Step 1: Redisチェック（24時間分）
  ├─ ヒット → 24時間分取得（部分的成功）
  └─ ミス or 不足 → Step 2へ

Step 2: S3読み込み（30日分）
  ├─ 成功 → 30日分取得
  │        → 最新24時間分をRedisにキャッシュ
  │        → 統計情報記録: source='s3'
  └─ 失敗 → Step 3へ

Step 3: yfinance API（30日分）
  ├─ 成功 → 30日分取得
  │        → 全データをRedisにキャッシュ
  │        → S3に保存（オプション）
  │        → 統計情報記録: source='yfinance', fallback_count=2
  └─ 失敗 → None返却
           → エラーログ記録

結果:
  - DataFrame or None
  - metadata: {
      'source': 使用したソース,
      'response_time': レスポンス時間,
      'row_count': 行数,
      'cache_hit': キャッシュヒット,
      'fallback_count': フォールバック回数
    }
```

---

## 📁 実装コンポーネント

### Component 1: S3MarketDataRepository（読み取り機能追加）

#### 現在の実装状況

```python
✅ 既存実装:
class S3MarketDataRepository:
    def save_ohlcv_data(self, df, symbol, timeframe) -> bool:
        # 日付ベースパーティショニングで保存
        # ✅ Phase 1で実装済み
```

#### S3データ構造

```
S3バケット: s3://tss-raw-data/

パーティション構造:
USDJPY/
├── H1/
│   ├── 2025/
│   │   ├── 10/
│   │   │   ├── 01/
│   │   │   │   └── data.parquet
│   │   │   ├── 02/
│   │   │   │   └── data.parquet
│   │   │   └── 15/
│   │   │       └── data.parquet
│   │   └── 11/
│   ├── 2024/
│   └── 2023/
├── M15/
└── D1/

パーティションキー例:
symbol='USDJPY', timeframe='H1', date='2025-10-15'
→ 'USDJPY/H1/2025/10/15/data.parquet'
```

#### 追加実装メソッド

```python
class S3MarketDataRepository(IMarketDataRepository):
    """S3永続化リポジトリ（読み取り機能追加）"""
    
    # ========================================
    # 主要メソッド
    # ========================================
    
    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        S3からOHLCVデータを読み込み
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
            timeframe: タイムフレーム（例: 'H1'）
            start_date: 開始日時（UTC）
            end_date: 終了日時（UTC）
            days: 過去N日分（start_date/end_dateより優先度低）
        
        Returns:
            pd.DataFrame: OHLCVデータ（index=timestamp_utc）
            None: データが存在しない場合
        
        処理フロー:
            1. 期間の正規化（days → start_date/end_date）
            2. パーティションキーリスト生成
            3. 各パーティションを並列読み込み
            4. DataFrame結合・ソート
            5. 期間フィルタリング
            6. 重複排除
        
        Example:
            # 過去30日分取得
            df = repo.load_ohlcv('USDJPY', 'H1', days=30)
            
            # 期間指定
            df = repo.load_ohlcv(
                'USDJPY', 'H1',
                start_date=datetime(2025, 10, 1, tzinfo=pytz.UTC),
                end_date=datetime(2025, 10, 15, tzinfo=pytz.UTC)
            )
        """
    
    def _generate_partition_keys(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        日付範囲からS3パーティションキーリストを生成
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            start_date: 開始日（UTC）
            end_date: 終了日（UTC）
        
        Returns:
            List[str]: S3キーのリスト
        
        Example:
            start: 2025-10-01, end: 2025-10-03
            → [
                'USDJPY/H1/2025/10/01/data.parquet',
                'USDJPY/H1/2025/10/02/data.parquet',
                'USDJPY/H1/2025/10/03/data.parquet'
              ]
        
        Note:
            - 日付単位でパーティション分割
            - 時刻は無視（00:00:00で正規化）
        """
    
    def _load_partition(
        self,
        key: str
    ) -> Optional[pd.DataFrame]:
        """
        単一パーティションからParquetファイルを読み込み
        
        Args:
            key: S3キー（例: 'USDJPY/H1/2025/10/15/data.parquet'）
        
        Returns:
            pd.DataFrame: OHLCVデータ
            None: ファイルが存在しない場合
        
        Raises:
            ValueError: Parquetフォーマットエラー
            ClientError: S3アクセスエラー
        
        エラーハンドリング:
            - NoSuchKey: ログ記録してNone返却
            - その他のS3エラー: 例外を投げる
            - Parquetエラー: 例外を投げる
        """
    
    def exists(
        self,
        symbol: str,
        timeframe: str,
        date: Optional[datetime] = None
    ) -> bool:
        """
        S3にデータが存在するか確認
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
            date: 確認する日付（Noneの場合は最新データ）
        
        Returns:
            bool: データが存在するか
        
        Example:
            # 特定日のデータ存在確認
            exists = repo.exists('USDJPY', 'H1', datetime(2025, 10, 15))
            
            # 最新データの存在確認
            exists = repo.exists('USDJPY', 'H1')
        """
    
    def get_available_range(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        利用可能なデータの期間を取得
        
        Args:
            symbol: 通貨ペア
            timeframe: タイムフレーム
        
        Returns:
            Tuple[datetime, datetime]: (最古日時, 最新日時)
            None: データが存在しない場合
        
        Note:
            - S3のパーティション一覧から判定
            - 実際のParquetファイルは読み込まない
        """
```

---

### Component 2: MarketDataProvider（統合プロバイダー）

#### クラス構造

```python
class MarketDataProvider:
    """
    統合マーケットデータプロバイダー
    
    責務:
        - ユースケース別の最適ソース選択
        - フォールバック戦略の実行
        - キャッシュ管理（Redisへの自動保存）
        - 統計情報の収集
        - エラーハンドリング
    
    データソース:
        - Redis (PriceCache): 24時間キャッシュ
        - MT5 (MT5DataCollector): リアルタイムデータ
        - S3 (S3MarketDataRepository): 過去データ
        - yfinance: フォールバック用API
    
    ユースケース:
        - trading: リアルタイム取引用（低レイテンシ）
        - chart: チャート表示用（中レイテンシ許容）
        - analysis: 分析・バックテスト用（大量データ）
    """
    
    def __init__(
        self,
        price_cache: PriceCache,
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
        
        Note:
            オプショナルなソースがNoneの場合、
            そのソースへのアクセスはスキップされる
        """
```

#### 主要メソッド

```python
def get_data(
    self,
    symbol: str,
    timeframe: str,
    period_days: int = 1,
    use_case: str = 'trading',
    force_source: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    """
    マーケットデータを取得
    
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
        # リアルタイム取引用（24時間）
        df, meta = provider.get_data('USDJPY', 'H1', 1, 'trading')
        
        # チャート表示用（30日）
        df, meta = provider.get_data('USDJPY', 'H1', 30, 'chart')
        
        # 分析用（90日）
        df, meta = provider.get_data('USDJPY', 'H1', 90, 'analysis')
        
        # デバッグ: S3を強制使用
        df, meta = provider.get_data(
            'USDJPY', 'H1', 30, force_source='s3'
        )
    
    処理フロー:
        1. use_caseとperiod_daysから優先順位決定
        2. 各ソースから順次取得を試行
        3. 成功したらRedisにキャッシュ（redis以外）
        4. 統計情報を更新
        5. DataFrame + metadataを返却
    """

def _get_source_priority(
    self,
    use_case: str,
    period_days: int,
    force_source: Optional[str]
) -> List[str]:
    """
    ユースケースと期間から優先順位を決定
    
    ロジック:
        - force_source指定時: [force_source]
        - trading + 24h以内: ['mt5', 'redis', 'yfinance']
        - trading + 24h超: ['mt5', 'yfinance']
        - chart + 24h以内: ['redis', 'mt5', 'yfinance']
        - chart + 24h超: ['redis', 's3', 'yfinance']
        - analysis + 24h以内: ['redis', 's3', 'yfinance']
        - analysis + 24h超: ['s3', 'redis', 'yfinance']
    """

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
        source: データソース名
        symbol: 通貨ペア
        timeframe: タイムフレーム
        period_days: 取得日数
    
    Returns:
        pd.DataFrame: OHLCVデータ
        None: データ取得失敗
    
    実装:
        - redis: PriceCache.load_ohlcv()
        - mt5: MT5DataCollector.fetch_ohlcv_data()
        - s3: S3MarketDataRepository.load_ohlcv()
        - yfinance: _fetch_from_yfinance()
    """

def _cache_result(
    self,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str
):
    """
    取得したデータをRedisにキャッシュ
    
    ルール:
        - 最新24時間分のみキャッシュ
        - それ以前のデータは破棄
        - キャッシュ失敗はログ記録のみ（例外を投げない）
    """

def get_stats(self) -> Dict[str, Any]:
    """
    統計情報を取得
    
    Returns:
        {
            'total_requests': int,
            'source_usage': {
                'redis': int,
                'mt5': int,
                's3': int,
                'yfinance': int
            },
            'avg_response_time': {
                'redis': float,
                'mt5': float,
                's3': float,
                'yfinance': float
            },
            'cache_hit_rate': float
        }
    """
```

---

## 📅 実装スケジュール

### Day 1-2: S3読み取り機能実装（所要: 2日）

#### Day 1午前: パーティションキー生成（2時間）

```python
タスク:
├─ _generate_partition_keys() 実装
├─ 日付範囲からS3キーリスト生成ロジック
├─ パーティションフォーマットの統一
└─ 単体テスト作成

実装内容:
def _generate_partition_keys(
    self, symbol, timeframe, start_date, end_date
):
    # 1. 日付リスト生成（start_date～end_date）
    # 2. 各日付をS3キーフォーマットに変換
    # 3. リスト返却

テストケース:
- 1日分のキー生成
- 30日分のキー生成
- 月跨ぎのキー生成
- 年跨ぎのキー生成
```

#### Day 1午後: 単一パーティション読み込み（3時間）

```python
タスク:
├─ _load_partition() 実装
├─ Parquetファイル読み込み
├─ エラーハンドリング（NoSuchKey等）
└─ 単体テスト作成

実装内容:
def _load_partition(self, key):
    # 1. S3からParquet取得
    # 2. pd.read_parquetで読み込み
    # 3. エラーハンドリング

エラーハンドリング:
- NoSuchKey → None返却（ログ記録）
- 権限エラー → 例外を投げる
- Parquetエラー → 例外を投げる

テストケース:
- 正常読み込み
- ファイル不存在
- フォーマットエラー
```

#### Day 2午前: メイン読み込みロジック（3時間）

```python
タスク:
├─ load_ohlcv() 実装
├─ 複数パーティション読み込み・結合
├─ フィルタリング・ソート
└─ 統合テスト

実装内容:
def load_ohlcv(self, symbol, timeframe, ...):
    # 1. 期間正規化
    # 2. パーティションキー生成
    # 3. 各パーティション読み込み（並列化検討）
    # 4. DataFrame結合
    # 5. 期間フィルタリング
    # 6. 重複排除・ソート

最適化:
- ThreadPoolExecutorで並列読み込み（検討）
- メモリ効率的な結合

テストケース:
- 1日分読み込み
- 30日分読み込み
- 部分的に欠損がある場合
- 全パーティションが存在しない場合
```

#### Day 2午後: 補助メソッド実装（2時間）

```python
タスク:
├─ exists() 実装
├─ get_available_range() 実装
└─ 統合テスト

実装内容:
def exists(self, symbol, timeframe, date):
    # S3オブジェクト存在確認
    # head_objectで軽量確認

def get_available_range(self, symbol, timeframe):
    # S3パーティション一覧取得
    # 最古・最新を判定

テストケース:
- データ存在確認
- データ範囲取得
- データが存在しない場合
```

---

### Day 3-4: MarketDataProvider実装（所要: 2日）

#### Day 3午前: 基本構造（2時間）

```python
タスク:
├─ クラス定義
├─ 初期化処理
├─ 統計情報構造
└─ 基本テスト

実装内容:
class MarketDataProvider:
    def __init__(self, ...):
        # データソース初期化
        # 統計情報初期化

テストケース:
- 初期化テスト
- 各データソースの注入確認
```

#### Day 3午後: ソース優先順位ロジック（3時間）

```python
タスク:
├─ _get_source_priority() 実装
├─ ユースケース別分岐
└─ 単体テスト

実装内容:
def _get_source_priority(self, use_case, period_days, force):
    # ユースケース・期間から優先順位決定
    # マトリックスに基づく分岐

テストケース:
- trading + 24h以内
- trading + 24h超
- chart + 24h以内
- chart + 24h超
- analysis + 全期間
- force_source指定時
```

#### Day 4午前: ソース別取得ロジック（3時間）

```python
タスク:
├─ _fetch_from_source() 実装
├─ 各ソースへの接続
├─ エラーハンドリング
└─ 単体テスト

実装内容:
def _fetch_from_source(self, source, ...):
    # ソース別分岐
    if source == 'redis': ...
    elif source == 'mt5': ...
    elif source == 's3': ...
    elif source == 'yfinance': ...

テストケース:
- 各ソースからの取得成功
- 各ソースからの取得失敗
- ソースがNoneの場合
```

#### Day 4午後: メインロジック実装（3時間）

```python
タスク:
├─ get_data() 実装
├─ フォールバック処理
├─ キャッシュ保存
├─ 統計情報更新
└─ 統合テスト

実装内容:
def get_data(self, symbol, timeframe, ...):
    # 1. 優先順位決定
    # 2. 各ソースから試行
    # 3. 成功時キャッシュ
    # 4. 統計更新
    # 5. metadata返却

テストケース:
- 1回目のソースで成功
- フォールバック発生
- 全ソース失敗
- キャッシュ保存確認
- 統計情報確認
```

---

### Day 5: 統合テストと最適化（所要: 1日）

#### 午前: エンドツーエンドテスト（3時間）

```python
シナリオ1: リアルタイム取引
  1. MT5から24時間分取得
  2. Redisにキャッシュされることを確認
  3. 2回目のリクエストでRedisヒットを確認

シナリオ2: チャート表示（30日）
  1. S3から30日分取得
  2. 直近24時間分がRedisにキャッシュされることを確認
  3. metadata確認（source='s3'）

シナリオ3: MT5障害時のフォールバック
  1. MT5を停止
  2. データ取得リクエスト
  3. Redisからフォールバック
  4. 最終的にyfinanceから取得

シナリオ4: 統計情報
  1. 複数回のリクエスト
  2. get_stats()で統計確認
  3. ソース使用率、レスポンス時間確認
```

#### 午後: パフォーマンス最適化（3時間）

```python
最適化項目:
├─ S3並列読み込み（ThreadPoolExecutor）
├─ キャッシュサイズ最適化
├─ レスポンス時間計測
└─ メモリ使用量確認

パフォーマンス目標:
├─ Redisキャッシュヒット: 10ms以内
├─ S3読み込み（30日分）: 5秒以内
├─ メモリ使用量: 50MB以内
└─ キャッシュヒット率: 60%以上

計測:
- 各ソースのレスポンス時間
- メモリ使用量（get_memory_usage()）
- キャッシュヒット率
```

---

## ✅ 成功判定基準

### 機能要件

- [ ] S3から指定期間のデータを読み込める
- [ ] MarketDataProviderがユースケース別に最適ソースを選択
- [ ] フォールバック処理が正常に動作
- [ ] Redisへの自動キャッシュが動作
- [ ] 統計情報が正確に収集される

### 非機能要件

| 項目 | 目標 | 測定方法 |
|------|------|---------|
| **S3読み込み** | 5秒以内（30日分） | time.time()計測 |
| **Redisヒット** | 10ms以内 | metadata['response_time'] |
| **メモリ使用量** | 50MB以内 | get_memory_usage() |
| **キャッシュヒット率** | 60%以上 | get_stats()['cache_hit_rate'] |
| **テストカバレッジ** | 80%以上 | pytest-cov |

### テスト要件

- [ ] 単体テスト: 全メソッドカバー
- [ ] 統合テスト: エンドツーエンドシナリオ
- [ ] エラーハンドリング: 全エラーケース
- [ ] パフォーマンステスト: 目標値達成

---

## 🔧 実装時の注意事項

### S3読み取り

```python
注意点:
1. パーティションが存在しない場合の処理
   - ログ記録してスキップ
   - 他のパーティションは処理継続

2. メモリ効率
   - 大量データは分割読み込み
   - 不要なカラムは読み込まない

3. エラーハンドリング
   - S3エラーは例外を投げる
   - ファイル不存在はNone返却
```

### MarketDataProvider

```python
注意点:
1. データソースの存在確認
   - Noneの場合はスキップ
   - 利用可能なソースのみ試行

2. キャッシュ保存
   - 24時間分のみ保存
   - 失敗しても例外を投げない

3. 統計情報
   - スレッドセーフに実装
   - リクエスト毎に更新
```

---

## 📊 Week 2完了後の状態

### 実装完了ファイル

```
src/infrastructure/persistence/s3/
├─ market_data_repository.py (拡張完了)
   ├─ load_ohlcv() ★追加
   ├─ _generate_partition_keys() ★追加
   ├─ _load_partition() ★追加
   ├─ exists() ★追加
   └─ get_available_range() ★追加

src/infrastructure/gateways/market_data/
└─ market_data_provider.py (新規作成) ★
   ├─ get_data()
   ├─ _get_source_priority()
   ├─ _fetch_from_source()
   ├─ _cache_result()
   └─ get_stats()

tests/unit/infrastructure/
├─ persistence/s3/
│  └─ test_market_data_repository.py (拡張)
└─ gateways/market_data/
   └─ test_market_data_provider.py (新規作成)

tests/integration/
└─ test_market_data_provider.py (新規作成)
```

### Phase 2進捗更新

```
Week 1: Redis基盤実装 ✅ 100%
Week 2: データアクセス層 ✅ 100%
Week 3: Streamlit統合 ⏳ 0%
Week 4: テスト・最適化 ⏳ 0%

Phase 2全体進捗: 60% → 80% ⬆️ +20%
```

---

## 🚀 次のステップ（Week 3予定）

```
Week 3: Streamlit統合
├─ chart_data_source.py更新
├─ MarketDataProvider利用
├─ キャッシュ設定最適化
└─ パフォーマンス測定

目標:
- チャート表示1秒以内
- MT5接続競合60%削減
- ユーザー体験向上
```

---

**END OF DOCUMENT**