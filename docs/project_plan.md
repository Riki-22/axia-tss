# AXIA 実装計画書 - クリーンアーキテクチャ移行

**作成日**: 2025年1月27日  
**対象期間**: 2025年1月27日 - 2月10日  
**目的**: 既存資産を活用したクリーンアーキテクチャへの段階的移行

---

## 1. エグゼクティブサマリー

### 1.1 現状分析
- ✅ **完成済み**: 
  - チャート表示UI (Streamlit)
  - テクニカル指標 (domain/technical_indicators)
  - マーケットデータゲートウェイ (yfinance, dummy_generator)
- ⚠️ **課題**: 
  - application層に配置された基盤コード
  - DynamoDBアクセスの直接実装
  - MT5接続の競合問題
- 🎯 **目標**: 
  - 2週間でクリーンアーキテクチャへ完全移行
  - 既存コードの95%は移動のみ（修正最小限）
  - 常に動作する状態を維持

### 1.2 基本方針
```
1. 動作するコードを壊さない
2. 移動 > 修正（既存ロジックは温存）
3. テスタビリティの向上
4. 段階的実装（毎日デプロイ可能）
```

---

## 2. アーキテクチャ設計

### 2.1 レイヤー責務の明確化

| レイヤー | 責務 | 主要コンポーネント |
|---------|------|-------------------|
| **Presentation** | ユーザー/外部IF | CLI, Streamlit UI |
| **Application** | ユースケース | 注文処理、データ収集 |
| **Domain** | ビジネスルール | エンティティ、バリデーション |
| **Infrastructure** | 技術的実装 | DB、ブローカー、メッセージング |

### 2.2 移行後のディレクトリ構造

```
src/
├── domain/                                   # ビジネスルール層
│   ├── entities/                            # 🆕 Phase1で作成
│   │   ├── order.py                        # 注文エンティティ
│   │   └── position.py                     # ポジションエンティティ
│   │
│   ├── repositories/                        # 🆕 Phase1で作成（インターフェース）
│   │   ├── order_repository.py             # 注文リポジトリI/F
│   │   └── kill_switch_repository.py       # Kill SwitchリポジトリI/F
│   │   # base_repository.py は任意（共通処理があれば）
│   │
│   └── services/
│       ├── order_validation.py             # ← validators.py 移動
│       └── technical_indicators/           # ✅ 既に一部実装済み
│           ├── pattern_detectors/
│           │   └── candlestick_patterns.py
│           └── level_detectors/
│               └── support_resistance.py
│
├── application/                             # ユースケース層
│   └── use_cases/
│       ├── order_processing/
│       │   └── process_sqs_order.py       # ← message_processor.py 移動
│       └── data_collection/
│           └── collect_market_data.py     # ← data_collector ロジック
│
├── infrastructure/                          # 技術的実装層
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py                    # 🆕 統合設定
│   │   ├── aws_config.py                  # ← config_loader.py 移動
│   │   └── mt5_config.py                  # ← config_loader_dc.py 移動
│   │
│   ├── gateways/
│   │   ├── brokers/
│   │   │   └── mt5/
│   │   │       ├── mt5_connection.py          # ← mt5_handler.py 分割
│   │   │       ├── mt5_order_executor.py      # ← mt5_handler.py 分割
│   │   │       ├── mt5_data_collector.py      # ← data_collector/main.py 分割
│   │   │       ├── mt5_proxy_service.py       # ⏳ Phase2で実装
│   │   │       ├── mt5_proxy_client.py        # ⏳ Phase2で実装
│   │   │       └── mt5_connection_manager.py  # ⏳ Phase2で実装
│   │   │
│   │   ├── market_data/
│   │   │   ├── market_data_provider.py        # 🆕 統合データプロバイダー
│   │   │   ├── dummy_generator.py             # ✅ 既に実装済み
│   │   │   └── yfinance_gateway.py            # ✅ 既に実装済み
│   │   │
│   │   └── messaging/
│   │       └── sqs/
│   │           ├── queue_listener.py          # ← main.py SQS部分
│   │           └── order_publisher.py         # ⏳ Phase2で実装
│   │
│   ├── persistence/
│   │   ├── dynamodb/
│   │   │   ├── base_dynamodb_repository.py    # 🆕 共通処理
│   │   │   ├── order_repository.py            # ← dynamodb_handler.py 分割
│   │   │   ├── kill_switch_repository.py      # ← dynamodb_handler.py 分割
│   │   │   ├── streamlit_repository.py        # ⏳ Phase2で移動
│   │   │   └── position_repository.py         # ⏳ Phase2で実装
│   │   │
│   │   ├── s3/
│   │   │   └── market_data_repository.py      # ← S3保存ロジック
│   │   │
│   │   └── redis/
│   │       ├── price_cache.py                 # ⏳ Phase2: 価格キャッシュ
│   │       ├── cache_manager.py               # ⏳ Phase2: キャッシュ戦略
│   │       └── proxy_communication.py         # ⏳ Phase2: Proxy通信
│   │
│   └── di/                                    # 🆕 依存性注入
│       └── container.py                       # DIコンテナ
│
└── presentation/                              # UI/CLI層
    ├── cli/
    │   ├── run_order_processor.py            # ← main.py エントリー
    │   ├── run_data_collector.py             # ← main.py エントリー
    │   └── run_mt5_proxy.py                  # ⏳ Phase2で実装
    │
    └── ui/
        └── streamlit/
            ├── app.py                         # メインアプリ
            │
            ├── controllers/                   # ⏳ Phase2で追加
            │   ├── order_controller.py       # UI注文制御
            │   └── dashboard_controller.py   # ダッシュボード制御
            │
            ├── components/
            │   └── trading_charts/
            │       ├── price_chart.py
            │       ├── chart_data_source.py
            │       ├── chart_indicators.py
            │       └── chart_renderer.py
            │
            ├── config/
            │   ├── page_config.py
            │   └── styles.py
            │
            ├── layouts/
            │   ├── header.py
            │   └── sidebar.py
            │
            ├── pages/
            │   ├── analysis_page.py
            │   ├── trading_page.py
            │   ├── position_page.py
            │   └── signal_page.py
            │
            ├── utils/
            │   └── trading_helpers.py
            │
            └── services/                     # ⏳ Phase2で削除予定
                └── dynamodb_service.py
```

**凡例**:
- ✅ 既に実装済み
- 🆕 Phase1で新規作成
- ⏳ Phase2以降で実装
- ← 既存ファイルからの移動/分割

---

## 3. 実装計画（2週間）

### Week 1: 基盤構築と移行（1/27-2/2）

#### Day 1-2: ドメイン層とインフラ基盤（1/27-28）
```python
# 最小限のエンティティ定義
@dataclass
class Order:
    ticket_id: str
    symbol: str
    lot_size: Decimal
    status: str = 'PENDING'
    
    @classmethod
    def from_sqs_message(cls, payload: dict) -> 'Order':
        """既存の辞書形式から変換"""
        return cls(
            ticket_id=payload['ticket_id'],
            symbol=payload['symbol'],
            lot_size=Decimal(str(payload['lot_size']))
        )
```

**作業内容**:
- [ ] domain/entities/order.py（シンプルなデータクラス）
- [ ] domain/repositories/インターフェース定義（order, kill_switch）
- [ ] infrastructure/config/settings.py（設定統合）
- [ ] infrastructure/di/container.py（基本実装）

#### Day 3-4: DynamoDBリポジトリ実装（1/29-30）
```python
class DynamoDBKillSwitchRepository(IKillSwitchRepository):
    """既存のcheck_kill_switch()をラップ"""
    def is_active(self) -> bool:
        # 既存ロジックをそのまま使用
        return existing_check_kill_switch()
```

**作業内容**:
- [ ] Kill Switchリポジトリ（既存ロジックをラップ）
- [ ] Orderリポジトリ（save処理を移動）
- [ ] domain/services/order_validation.py（validators.py移動）

#### Day 5: MT5ゲートウェイとデータプロバイダー（1/31）
**作業内容**:
- [ ] mt5_connection.py（接続管理）
- [ ] mt5_order_executor.py（注文実行）
- [ ] mt5_data_collector.py（データ収集＋S3保存）
- [ ] market_data_provider.py（データソース統合）

```python
# Phase1: シンプルな実装
class MarketDataProvider:
    """データソース統合（キャッシュなし）"""
    def get_latest_price(self, symbol: str):
        if self.mt5.is_connected():
            return self.mt5.get_current_price(symbol)
        return self.yfinance.get_latest(symbol)
```

#### Weekend: 統合テスト（2/1-2）
- [ ] order_manager全体の動作確認
- [ ] 旧コードとの並行稼働テスト
- [ ] バグ修正とログ確認

### Week 2: 完成と最適化（2/3-10）

#### Day 6-7: data_collector移行（2/3-4）
- [ ] mt5_data_collector.py（S3保存込み）
- [ ] collect_market_data.py ユースケース（簡略版）
- [ ] run_data_collector.py CLIランナー

#### Day 8-9: Streamlit連携準備（2/5-6）
- [ ] MarketDataProviderとStreamlitの統合
- [ ] チャートコンポーネントの修正
- [ ] データソース切り替え機能

#### Day 10: Phase2準備（2/7-10）
- [ ] Redis統合設計
- [ ] キャッシュ戦略の検討
- [ ] パフォーマンステスト
- [ ] ドキュメント整理

---

## 4. 移行作業の詳細

### 4.1 ファイル移動マッピング

#### order_manager/の移動

| 既存ファイル | 移行先 | 作業 |
|------------|--------|------|
| application/order_manager/main.py | → presentation/cli/run_order_processor.py<br>→ infrastructure/gateways/messaging/sqs/queue_listener.py | 分割 |
| application/order_manager/message_processor.py | → application/use_cases/order_processing/process_sqs_order.py | 移動 |
| application/order_manager/mt5_handler.py | → infrastructure/gateways/brokers/mt5/mt5_connection.py<br>→ infrastructure/gateways/brokers/mt5/mt5_order_executor.py | 分割 |
| application/order_manager/dynamodb_handler.py | → infrastructure/persistence/dynamodb/order_repository.py<br>→ infrastructure/persistence/dynamodb/kill_switch_repository.py | 分割 |
| application/order_manager/validators.py | → domain/services/order_validation.py | 移動 |
| application/order_manager/config_loader.py | → infrastructure/config/aws_config.py | 移動/統合 |

#### data_collector/の移動

| 既存ファイル | 移行先 | 作業 |
|------------|--------|------|
| application/data_collector/main.py | → presentation/cli/run_data_collector.py<br>→ infrastructure/gateways/brokers/mt5/mt5_data_collector.py | 分割（S3保存込み） |
| application/data_collector/config_loader_dc.py | → infrastructure/config/mt5_config.py | 移動/統合 |

#### 新規作成

| 新規ファイル | 目的 | Phase |
|------------|------|-------|
| infrastructure/gateways/market_data/market_data_provider.py | データソース統合 | Phase1 |
| infrastructure/persistence/redis/price_cache.py | Redisキャッシュ | Phase2 |
| infrastructure/persistence/redis/cache_manager.py | キャッシュ戦略 | Phase2 |

#### streamlit関連（Phase2）

| 既存ファイル | 状態 | Phase2での作業 |
|------------|------|---------------|
| presentation/ui/streamlit/services/dynamodb_service.py | 現状維持 | → infrastructure/persistence/dynamodb/streamlit_repository.py |
| presentation/ui/streamlit/app.py | 現状維持 | コントローラー統合 |

### 4.2 インポート修正戦略

```python
# 旧インポート
from config_loader import QUEUE_URL, sqs_client
from message_processor import process_message

# 新インポート（一括置換で対応）
from infrastructure.config.settings import settings
from application.use_cases.order_processing.process_sqs_order import ProcessSQSOrderUseCase
```

**VSCode一括置換パターン**:
```
Find: from config_loader import
Replace: from infrastructure.config.settings import settings\n# from config_loader import

Find: from message_processor import
Replace: from application.use_cases.order_processing.process_sqs_order import
```

## 5. データソース戦略

### 5.1 データソース優先順位
```
1. Redis（キャッシュ） - Phase2で実装
   ↓ なければ
2. MT5（リアルタイム） - メインソース
   ↓ 接続不可なら
3. yfinance（フォールバック） - 代替ソース
   ↓ ネットワーク不可なら
4. dummy_generator（モック） - 開発/テスト用
```

### 5.2 Phase1実装（シンプル版）
```python
# infrastructure/gateways/market_data/market_data_provider.py
class MarketDataProvider:
    """データソース統合（Phase1: キャッシュなし）"""
    
    def __init__(self):
        self.mt5 = MT5DataCollector()
        self.yfinance = YFinanceGateway()
        self.dummy = DummyGenerator()
    
    def get_latest_price(self, symbol: str) -> float:
        """最新価格取得"""
        if self.mt5.is_connected():
            return self.mt5.get_current_price(symbol)
        elif self._network_available():
            return self.yfinance.get_latest(symbol)
        else:
            return self.dummy.generate_price(symbol)
    
    def get_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """OHLCV取得"""
        if self.mt5.is_connected():
            return self.mt5.get_rates(symbol, timeframe)
        elif self._network_available():
            return self.yfinance.fetch_ohlcv(symbol, timeframe)
        else:
            return self.dummy.generate_ohlcv(symbol, timeframe)
```

### 5.3 Phase2実装（Redis統合）
```python
# Phase2で追加
def get_latest_price(self, symbol: str) -> float:
    # Redisキャッシュ確認
    cached = self.cache.get_price(symbol)
    if cached and self._is_fresh(cached):
        return cached['price']
    
    # ソースから取得
    price = self._fetch_from_source(symbol)
    
    # キャッシュ更新
    self.cache.set_price(symbol, price, ttl=5)
    return price
```

---

## 6. リスク管理と対策

### 5.1 主要リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| インポートエラー | 高 | 段階的修正、import文のバックアップ |
| MT5接続競合 | 高 | Phase1: 排他制御、Phase2: Proxy |
| DynamoDB不整合 | 中 | 既存ロジックを温存、ラップのみ |
| テスト不足 | 中 | 各段階で動作確認、ログ強化 |

### 5.2 ロールバック戦略

```bash
# バックアップ作成
cp -r src/application/order_manager src/application/order_manager.backup
cp -r src/application/data_collector src/application/data_collector.backup

# 問題発生時は元に戻す
mv src/application/order_manager.backup src/application/order_manager
```

---

## 6. 成功の判断基準

### 6.1 Phase1完了条件（Week1）
- ✅ order_managerが新構造で動作
- ✅ SQSメッセージ受信が正常
- ✅ Kill Switch機能が動作
- ✅ MT5注文実行が可能
- ✅ DynamoDB保存が正常

### 6.2 Phase2完了条件（Week2）
- ✅ data_collectorが移行完了
- ✅ Streamlit UIから注文可能
- ✅ すべてのテストがパス
- ✅ 旧ディレクトリ削除完了
- ✅ ドキュメント更新完了

---

## 7. 日次チェックリスト

### Day 1 (1/27)
```markdown
Morning (4h):
- [ ] プロジェクト構造作成
- [ ] domain/entities/order.py
- [ ] domain/repositories/インターフェース

Afternoon (4h):
- [ ] infrastructure/config/settings.py
- [ ] infrastructure/di/container.py
- [ ] 基本動作確認

完了判定:
- [ ] 新構造でimportエラーなし
- [ ] 設定ファイル読み込み成功
```

### Day 2 (1/28)
```markdown
Morning (4h):
- [ ] DynamoDBリポジトリ基底クラス
- [ ] Kill Switchリポジトリ実装

Afternoon (4h):
- [ ] Orderリポジトリ実装
- [ ] リポジトリのテスト

完了判定:
- [ ] Kill Switch確認が動作
- [ ] 注文保存が動作
```

### Day 3 (1/29)
```markdown
Morning (4h):
- [ ] MT5接続クラス実装
- [ ] MT5注文実行クラス実装

Afternoon (4h):
- [ ] SQSリスナー実装
- [ ] ユースケース統合

完了判定:
- [ ] MT5接続成功
- [ ] 注文実行テスト成功
```

### Day 4 (1/30)
```markdown
Morning (4h):
- [ ] ProcessSQSOrderUseCase完成
- [ ] CLIランナー実装

Afternoon (4h):
- [ ] エンドツーエンドテスト
- [ ] ログ確認とデバッグ

完了判定:
- [ ] order_manager完全動作
- [ ] 旧版との互換性確認
```

### Day 5 (1/31)
```markdown
Morning (4h):
- [ ] data_collector分析
- [ ] MT5データ収集クラス実装

Afternoon (4h):
- [ ] S3リポジトリ実装
- [ ] data_collectorテスト

完了判定:
- [ ] データ収集動作確認
- [ ] S3保存成功
```

---

## 8. コマンドライン作業

### 初期セットアップ
```bash
# 完全なディレクトリ構造作成
mkdir -p src/domain/{entities,repositories,services/technical_indicators/{pattern_detectors,level_detectors}}
mkdir -p src/application/use_cases/{order_processing,data_collection}
mkdir -p src/infrastructure/{config,di}
mkdir -p src/infrastructure/persistence/{dynamodb,s3,redis}
mkdir -p src/infrastructure/gateways/brokers/mt5
mkdir -p src/infrastructure/gateways/market_data
mkdir -p src/infrastructure/gateways/messaging/sqs
mkdir -p src/presentation/{cli,ui/streamlit/{controllers,components/price_charts,config,layouts,pages,utils,services}}

# __init__.py ファイルの作成
find src -type d -exec touch {}/__init__.py \;

# バックアップ作成
tar -czf backup_$(date +%Y%m%d).tar.gz src/application/order_manager src/application/data_collector
```

### 移動コマンド（実際のパス）
```bash
# Phase1: order_manager移動
mv src/application/order_manager/validators.py \
   src/domain/services/order_validation.py

mv src/application/order_manager/message_processor.py \
   src/application/use_cases/order_processing/process_sqs_order.py

mv src/application/order_manager/config_loader.py \
   src/infrastructure/config/aws_config.py

# Phase1: data_collector移動  
mv src/application/data_collector/config_loader_dc.py \
   src/infrastructure/config/mt5_config.py

# インポート一括修正
find src -name "*.py" -exec sed -i 's/from validators import/from domain.services.order_validation import/g' {} \;
find src -name "*.py" -exec sed -i 's/from message_processor import/from application.use_cases.order_processing.process_sqs_order import/g' {} \;
find src -name "*.py" -exec sed -i 's/from config_loader import/from infrastructure.config.aws_config import/g' {} \;
```

### テスト実行
```bash
# 段階的テスト
python src/presentation/cli/run_order_processor.py --test-mode
python -m pytest tests/integration/test_order_flow.py -v
```

---

## 9. 緊急時対応

### トラブルシューティング
```python
# デバッグモード実行
import logging
logging.basicConfig(level=logging.DEBUG)

# 接続テスト
def test_connections():
    assert test_dynamodb_connection()
    assert test_sqs_connection()
    assert test_mt5_connection()
```

### ロールバック手順
1. 現在の変更を退避: `git stash`
2. バックアップから復元: `tar -xzf backup_YYYYMMDD.tar.gz`
3. 設定ファイル確認: `.env`ファイルの復元
4. サービス再起動

---

## 10. 完了後のNext Steps

### Phase2（Week 3-4）
- **Redis統合**: 
  - price_cache.py実装
  - cache_manager.py実装
  - MarketDataProviderへのキャッシュ層追加
- **Streamlit連携強化**:
  - controllersパターン導入
  - 注文パネル統合
  - データソース選択UI
- **Position管理**:
  - positionエンティティ追加
  - position_repository実装

### Phase3（将来）
- **MT5 Proxyサービス**:
  - 接続競合の根本解決
  - Redis経由の通信
- **高度な機能**:
  - Value Objects導入
  - Domain Events実装
  - イベントソーシング
- **パフォーマンス最適化**:
  - 非同期処理の強化
  - バッチ処理の最適化

### ドキュメント更新
- README.md
- API仕様書
- デプロイメント手順
- トラブルシューティングガイド

---

**この計画に従い、既存資産を最大限活用しながら、2週間でクリーンアーキテクチャへの移行を完了させます。**