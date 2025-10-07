# AXIA 実装計画書

**作成日**: 2025年10月8日  
**対象期間**: 2025年10月8日 - 10月31日  
**目的**: 既存資産を活用したクリーンアーキテクチャへの移行と実データ連携実装

---

## 1. エグゼクティブサマリー

### 1.1 現状
- **完成済み**: チャート表示、パターン検出（domain/technical_indicators）
- **課題**: application層に配置されたインフラ寄りのコード（order_manager, data_collector）
- **制約**: 10/31退職までに転職ポートフォリオとして完成必須

### 1.2 目標
- 既存コードを適切な層に再配置（クリーンアーキテクチャ準拠）
- 実データ連携の実現（MT5/yfinance）
- UI統合による注文実行機能
- MT5接続の競合問題解決

### 1.3 基本方針
- **既存コードの95%は修正せず移動のみ**
- **インポートパスの修正で対応**
- **段階的実装で常に動作する状態を維持**

---

## 2. アーキテクチャ設計

### 2.1 レイヤー構成

```
┌─────────────────────────────────────────────┐
│         Presentation Layer (UI/CLI)          │
├─────────────────────────────────────────────┤
│        Application Layer (Use Cases)         │
├─────────────────────────────────────────────┤
│         Domain Layer (Business Rules)        │
├─────────────────────────────────────────────┤
│     Infrastructure Layer (Technical Details) │
└─────────────────────────────────────────────┘
```

### 2.2 最終ディレクトリ構造

```
src/
├── domain/                                    # ビジネスルール層
│   ├── technical_indicators/                  # ✅ 実装済み
│   │   ├── pattern_detectors/
│   │   └── level_detectors/
│   └── services/
│       └── order_validation.py               # validators.py を移動
│
├── application/                               # ユースケース層
│   └── use_cases/
│       ├── order_processing/
│       │   └── process_sqs_order.py         # message_processor.py を移動
│       └── data_collection/
│           └── collect_market_data.py       # data_collector ロジック
│
├── infrastructure/                            # 技術的実装層
│   ├── gateways/
│   │   ├── brokers/
│   │   │   └── mt5/
│   │   │       ├── mt5_connection.py            # mt5_handler.py 分割
│   │   │       ├── mt5_order_executor.py        # mt5_handler.py 分割
│   │   │       ├── mt5_proxy_service.py         # 新規：Proxy本体
│   │   │       ├── mt5_proxy_client.py          # 新規：Proxyクライアント
│   │   │       └── mt5_connection_manager.py    # 新規：接続管理
│   │   ├── market_data/
│   │   │   ├── data_source_interface.py         # 新規：統合インターフェース
│   │   │   ├── dummy_generator.py               # ✅ 実装済み
│   │   │   ├── mt5_data_gateway.py              # data_collector 分割
│   │   │   └── yfinance_gateway.py              # ✅ 実装済み
│   │   └── messaging/
│   │       └── sqs/
│   │           ├── queue_listener.py            # main.py SQS部分
│   │           └── order_publisher.py           # 新規：注文送信
│   │
│   ├── persistence/
│   │   ├── dynamodb/
│   │   │   ├── order_repository.py          # dynamodb_handler.py 分割
│   │   │   ├── kill_switch_repository.py    # dynamodb_handler.py 分割
│   │   │   ├── streamlit_repository.py      # dynamodb_service.py 移動
│   │   │   └── position_repository.py       # 新規
│   │   ├── s3/
│   │   │   └── market_data_repository.py    # S3保存ロジック
│   │   └── redis/
│   │       ├── price_cache.py               # 新規：価格キャッシュ
│   │       └── proxy_communication.py       # 新規：Proxy通信
│   │
│   └── config/
│       ├── settings.py                      # 新規：統合設定
│       ├── aws_config.py                    # config_loader.py 移動
│       └── mt5_config.py                    # config_loader_dc.py 移動
│
└── presentation/                              # UI/CLI層
    ├── cli/
    │   ├── run_order_processor.py           # main.py エントリー
    │   ├── run_data_collector.py            # main.py エントリー
    │   └── run_mt5_proxy.py                 # 新規：Proxy起動
    │
    └── ui/
        └── streamlit/
            ├── app.py                        
            ├── components/
            │   └── price_charts/
            │       ├── price_chart.py            
            │       ├── chart_data_source.py      
            │       ├── chart_indicators.py       
            │       └── chart_renderer.py         
            ├── config
            │   ├── page_config.py
            │   └── styles.py
            ├── layouts
            │   ├── header.py
            │   └── sidebar.py
            ├── pages
            │   ├── analysis_page.py
            │   ├── chart_page.py
            │   ├── position_page.py
            │   └── signal_page.py
            │── utils
            │   └── trading_helpers.py
            └── services/                     # 削除予定
                └── dynamodb_service.py

```

---

## 3. 実装計画

### 3.1 既存ファイルの移動マッピング

#### order_manager/ の分解

| 既存ファイル | 移動先 | 作業内容 |
|------------|--------|---------|
| `main.py` | `infrastructure/messaging/sqs/queue_listener.py`<br>`presentation/cli/run_order_processor.py` | SQS部分とエントリーポイントに分割 |
| `message_processor.py` | `application/use_cases/order_processing/process_sqs_order.py` | そのまま移動 |
| `mt5_handler.py` | `infrastructure/brokers/mt5/mt5_connection.py`<br>`infrastructure/brokers/mt5/mt5_order_executor.py` | 接続と実行に分割 |
| `dynamodb_handler.py` | `infrastructure/persistence/dynamodb/order_repository.py`<br>`infrastructure/persistence/dynamodb/kill_switch_repository.py` | 機能別に分割 |
| `validators.py` | `domain/services/order_validation.py` | そのまま移動 |
| `config_loader.py` | `infrastructure/config/aws_config.py` | そのまま移動 |

#### data_collector/ の分解

| 既存ファイル | 移動先 | 作業内容 |
|------------|--------|---------|
| `main.py` | `infrastructure/brokers/mt5/mt5_data_gateway.py`<br>`infrastructure/persistence/s3/market_data_repository.py`<br>`presentation/cli/run_data_collector.py` | 機能別に3分割 |
| `config_loader_dc.py` | `infrastructure/config/mt5_config.py` | そのまま移動 |

#### streamlit/services/ の移動

| 既存ファイル | 移動先 | 作業内容 |
|------------|--------|---------|
| `dynamodb_service.py` | `infrastructure/persistence/dynamodb/streamlit_repository.py` | 移動＋クラス名変更 |

---

## 4. 実装スケジュール

### Week 1: 基盤整備（10/8-13）

#### Day 1: 10/8（火）- 構造準備とファイル移動
```bash
# 作業時間: 4時間
09:00-10:00  ディレクトリ構造作成
10:00-12:00  ファイル移動実行
13:00-14:00  基本的な動作確認
```

**実行コマンド**:
```bash
# ディレクトリ作成
mkdir -p src/domain/services
mkdir -p src/application/use_cases/{order_processing,data_collection}
mkdir -p src/infrastructure/{brokers/mt5,persistence/{dynamodb,s3,redis}}
mkdir -p src/infrastructure/{messaging/sqs,config}
mkdir -p src/presentation/cli

# ファイル移動
mv src/application/order_manager/validators.py src/domain/services/order_validation.py
mv src/application/order_manager/message_processor.py src/application/use_cases/order_processing/process_sqs_order.py
# ... (詳細は実装時に)
```

#### Day 2: 10/9（水）- インポート修正と接続管理
```yaml
09:00-11:00: インポートパス一括修正
11:00-13:00: MT5ConnectionManager実装
14:00-16:00: 排他制御のテスト
```

**主要タスク**:
- VSCodeの一括置換でインポートパス修正
- MT5接続の排他制御実装

#### Day 3: 10/10（木）- Redis統合
```yaml
09:00-12:00: Redis価格キャッシュ実装
13:00-16:00: キャッシュ統合テスト
```

#### Day 4-5: 10/11-12（金土）- UI統合
```yaml
金曜:
  - order_panel.py実装
  - SQS連携テスト
土曜:
  - position_table.py実装
  - エンドツーエンドテスト
```

#### Day 6: 10/13（日）- バッファ
```yaml
- バグ修正
- ドキュメント更新
- Phase 2準備
```

### Week 2: MT5 Proxy実装（10/14-20）

#### 10/14-16: Proxyサービス開発
- `mt5_proxy_service.py` 実装
- `mt5_proxy_client.py` 実装
- Redis通信層の実装

#### 10/17-20: 統合とテスト
- 全プロセスをProxy経由に切り替え
- パフォーマンステスト
- 負荷テスト

### Week 3: ポートフォリオ化（10/21-27）

#### 10/21-23: ドキュメント作成
- README.md完成
- アーキテクチャ図作成
- API仕様書

#### 10/24-27: デモ準備
- デモ動画作成
- GitHub整理
- 最終テスト

---

## 5. MT5接続管理戦略

### 5.1 Phase 1: 排他制御（今週）

```python
# 簡易的な排他制御
class MT5ConnectionManager:
    def acquire_connection(process_name: str) -> bool:
        # Redisでロック管理
        pass
```

### 5.2 Phase 2: Proxyサービス（来週）

```
┌──────────────┐     Redis      ┌─────────────┐
│Order Manager │ ←───────────→  │             │
├──────────────┤                 │  MT5 Proxy  │
│Data Collector│ ←───────────→  │   Service   │ ←──→ MT5
├──────────────┤                 │             │
│ Streamlit UI │ ←───────────→  │             │
└──────────────┘                 └─────────────┘
```

---

## 6. リスク管理

### 6.1 識別されたリスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| MT5接続競合 | 高 | 高 | Phase 1で排他制御、Phase 2でProxy |
| インポートエラー | 中 | 中 | 段階的な修正、十分なテスト |
| 時間不足 | 高 | 中 | 優先順位の明確化、MVP思考 |
| データ不整合 | 中 | 低 | トランザクション管理、ログ強化 |

### 6.2 コンティンジェンシープラン

1. **MT5接続が不安定な場合**: モックデータでの動作を保証
2. **リファクタリングで動作しない場合**: 元の構造にロールバック
3. **時間が不足する場合**: UI機能を優先、Proxy実装は後回し

---

## 7. 成功指標（KPI）

### 7.1 技術的指標
- [ ] 全既存テストがパス
- [ ] エンドツーエンドテスト成功
- [ ] MT5接続エラー率 < 1%
- [ ] 平均レスポンス時間 < 500ms

### 7.2 ビジネス指標
- [ ] デモ可能な状態（10/15まで）
- [ ] GitHub公開可能（10/25まで）
- [ ] ポートフォリオ完成（10/31まで）

---

## 8. 作業チェックリスト

### Phase 1: ファイル移動（10/8）
- [ ] ディレクトリ構造作成
- [ ] order_manager ファイル移動
- [ ] data_collector ファイル移動
- [ ] dynamodb_service 移動
- [ ] 基本動作確認

### Phase 2: インポート修正（10/9）
- [ ] order_processing インポート修正
- [ ] data_collection インポート修正
- [ ] infrastructure層 インポート修正
- [ ] presentation層 インポート修正
- [ ] 単体テスト実行

### Phase 3: 新機能実装（10/10-13）
- [ ] MT5ConnectionManager 実装
- [ ] Redis価格キャッシュ 実装
- [ ] order_panel.py 実装
- [ ] position_table.py 実装
- [ ] 統合テスト

### Phase 4: Proxy実装（10/14-20）
- [ ] mt5_proxy_service.py 実装
- [ ] mt5_proxy_client.py 実装
- [ ] 全プロセス統合
- [ ] 負荷テスト

---
