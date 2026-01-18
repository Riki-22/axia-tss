# AXIA Trading Strategy System

**An integrated platform designed to sublimate trading from a personal 'art' into an analyzable, repeatable, and sustainable 'science'.**

**Last Updated**: 2026-01-13  
**Version**: 2.0.0  
**Implementation Status**: Phase 1-3: 100% Complete

[![Project Status](https://img.shields.io/badge/status-active-green.svg)](https://github.com/Riki-22/axia-tss)
[![AWS](https://img.shields.io/badge/AWS-Deployed-orange.svg)](docs/physical_design/aws_architecture.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Implementation](https://img.shields.io/badge/phase%201--3-100%25%20complete-brightgreen.svg)](docs/implementation/current_status.md)

---

## プロジェクト概要

**AXIA Trading Strategy System** は感情や認知バイアスを排除し、自動取引を通じて持続可能な収益を実現することを目的とした個人投資家向け取引システムです。

### 主要な特徴

#### リアルタイムUI (Real-time UI)

Streamlitを使用し、リアルタイムの価格チャート、口座情報、現在のポジション・損益（P&L）、証拠金維持率、パターン検出など表示

- **ダッシュボード**

  ![trading_page](docs/asset/trading_page.png)

- **ポジション情報**

  ![position_page](docs/asset/position_page.png)

- **パターン検出**

  ![analyze_page](docs/asset/analyze_page.png)

#### 注文システム (SQS Order System)

StreamlitのUIから送信された注文リクエストをSQS（メッセージキュー）を介して非同期で処理し、EC2サーバー上のMT5（MetaTrader 5）で注文を自動実行

- **注文パネル**

  ![order_panel](docs/asset/order_panel.png)

#### システムアーキテクチャ (System Architecture)

- **システム全体構成**

  ![aws_architecture](docs/asset/aws_architecture.png)

- **クリーンアーキテクチャ**

  ビジネスロジックと技術的詳細を分離する「クリーンアーキテクチャ」と「DDD（ドメイン駆動設計）」、および「依存性注入（DI）」パターンを採用しており、テストや保守が容易な設計

  ```mermaid
  graph TB
      subgraph "User Interface"
          UI[Streamlit UI]
          CLI[CLI Scripts]
      end

      subgraph "External World"
          UI[Streamlit UI]
          CLI[CLI Scripts]
          Broker[MT5 Broker]
          AWS[AWS Services]
      end
      
      subgraph "Clean Architecture Layers"
          subgraph "Presentation Layer"
              Controllers[Controllers]
              Presenters[Presenters]
          end
          
          subgraph "Application Layer"
              UseCases[Use Cases]
              AppServices[Application Services]
          end
          
          subgraph "Domain Layer"
              Entities[Entities]
              DomainServices[Domain Services]
              Repositories[Repository Interfaces]
          end
          
          subgraph "Infrastructure Layer"
              RepositoryImpl[Repository Implementations]
              Gateways[External Gateways]
              Frameworks[Frameworks & Drivers]
          end
      end
      
      UI --> Controllers
      CLI --> Controllers
      Controllers --> UseCases
      UseCases --> DomainServices
      UseCases --> Repositories
      Repositories -.-> RepositoryImpl
      RepositoryImpl --> AWS
      Gateways --> Broker
  ```

#### 統合データ戦略 (Data Integration)

「3階層データ戦略」（Hot: Redis / Warm: DynamoDB / Cold: S3）を採用。Redis（キャッシュ）、MT5（リアルタイム）、S3（履歴）、yfinance（フォールバック）といった複数のデータソースを透過的に扱う「統合データプロバイダー」を実装、パフォーマンスと可用性を両立

```mermaid
graph TB
    subgraph "Data Access Patterns"
        subgraph "Hot Data (Redis)"
            direction TB
            HotAccess[高頻度アクセス<br/>ミリ秒応答]
            RealtimePrice[リアルタイム価格]
            ActivePos[アクティブポジション]
            RecentOHLCV[24時間OHLCV]
        end
        
        subgraph "Warm Data (DynamoDB)"
            direction TB
            WarmAccess[中頻度アクセス<br/>低レイテンシ]
            TradingRecords[取引記録]
            OrderHistory[注文履歴]
            SystemConfig[システム設定]
        end
        
        subgraph "Cold Data (S3)"
            direction TB
            ColdAccess[低頻度アクセス<br/>大容量]
            HistoricalOHLCV[ヒストリカルOHLCVデータ]
        end
    end
        
    classDef hot fill:#ffebee,color:#000
    classDef warm fill:#e8f5e8,color:#000
    classDef cold fill:#e1f5fe,color:#000
    
    class RealtimePrice,ActivePos,RecentOHLCV hot
    class TradingRecords,OrderHistory,SystemConfig warm
    class HistoricalOHLCV,BacktestResults,SystemLogs cold
```

#### リスク管理 (Risk Management)

取引の緊急停止を行うための「Kill Switch」機能が実装されており、その状態をDynamoDBで永続的に管理。また、注文時のバリデーション（検証）も実装

```mermaid
stateDiagram-v2
    [*] --> Inactive: システム起動
    
    Inactive --> Active: 手動有効化
    Inactive --> Active: 自動トリガー
    
    Active --> Inactive: 手動無効化
    
    state Active {
        [*] --> Monitoring: 有効化
        Monitoring --> BlockOrders: 注文ブロック
        BlockOrders --> Monitoring: 継続監視
    }
    
    state "自動トリガー条件" as AutoTrigger {
        DailyLoss: 日次損失制限
        Drawdown: ドローダウン制限
        SystemError: システムエラー
    }
```

#### バックテスト (Backtesting)

SageMaker JupyterLab環境で開発・検証中。Phase 5で本番システムに統合予定。

**既存実装（Jupyter）**:
- テクニカル分析（ダウ理論、S/Rゾーン、ピボット）
- 4種シグナル生成（S/R、RSI、MACD、ボリンジャーバンド）
- 投票システムによるシグナル統合
- vectorbtバックテストエンジン
- リスク管理（RR比1.5倍、トレーリングストップ）

**テスト結果例**:
```
--- 分析結果（サマリー）---
トレンド方向: Range/Unclear
トレンド強度: Weak/Ranging
直近のサポート: [147.248, 147.087, 146.663]
直近のレジスタンス: [147.524]

【ポートフォリオ パフォーマンスレポート】
期間                          2025-01-01 ~ 2025-07-11 (109日)
初期資金                      1,000,000円
最終資金                      1,021,291円
Total Return [%]              2.13%
Benchmark Return [%]          -6.20%
Max Drawdown [%]              0.90%
Sharpe Ratio                  2.34
Sortino Ratio                 4.99
Win Rate [%]                  72.73%
```

- **分析結果（グラフ）**

  ![backtest_analysis](docs/asset/backtest_analysis.png)

  ![backtest_summary](docs/asset/backtest_summary.png)
  
#### パフォーマンスとコスト効率 (Performance & Cost)

EC2 t3.mediumインスタンスと各種AWSマネージドサービスを組み合わせて、月額約$50以下での運用を実現

- **月額予算上限**: $50.00 (約7,500円)  
- **現在の月額コスト**: $43-47 (約6,450-7,050円)  
- **予算残余**: $3-7 (約450-1,050円) = 6-14%のバッファー

```mermaid
pie title 月額コスト内訳 ($43-47)
    "EC2 Instance (t3.medium)" : 30
    "ElastiCache (t4g.micro)" : 13
    "DynamoDB" : 1
    "S3 Storage" : 1
    "SQS" : 1
    "CloudWatch" : 1
```

---

## 技術スタック

### バックエンド
- **言語**: Python 3.11
- **アーキテクチャ**: Clean Architecture + Domain-Driven Design
- **依存性注入**: Dependency Injector (Python)
- **データ検証**: Pydantic

### インフラストラクチャ（AWS）

| サービス | 用途 |
|---------|------|
| **EC2** (t3.small) | アプリケーション実行 |
| **ElastiCache** (t4g.micro) | Redisキャッシュ |
| **DynamoDB** (On-Demand) | 注文履歴・Kill Switch |
| **S3** (Standard) | 長期データ保存 |
| **SQS** (Standard) | 非同期注文処理 |
| **CloudWatch** | 監視・ログ |
| **Secrets Manager** | 認証情報管理 |
| **VPC** | ネットワーク |

### データベース
- **Redis** (ElastiCache): ホットキャッシュ、15-94ms応答
- **DynamoDB**: 注文履歴、Kill Switch状態
- **S3**: 長期OHLCVデータ、パーティション設計

### 外部連携
- **MetaTrader 5 (MT5)**: 取引実行、リアルタイムデータ取得
- **yfinance**: バックアップデータソース

### UI/監視
- **Streamlit**: リアルタイムダッシュボード、手動操作インターフェース
- **Plotly**: インタラクティブチャート

### 開発・運用
- **Git/GitHub**: バージョン管理
- **pytest**: ユニットテスト（カバレッジ 86%）
- **Task Scheduler**: Windows自動起動（4プロセス）
- **CloudWatch**: ログ・メトリクス監視

---

## 主要機能

### 1. 統合データアクセス層（OhlcvDataProvider）

```python
# 4つのデータソースを透過的に統合、自動フォールバック
sources = [Redis, MT5, S3, yfinance]
data = provider.get_data(
    symbol="USDJPY",
    timeframe="H1",
    use_case="trading"  # trading/chart/analysis
)
# Redis → MT5 → S3 → yfinance の順で自動フォールバック
```

**特徴**:
- 複数ソース統合（Redis/MT5/S3/yfinance）
- ユースケース別最適化（trading/chart/analysis）
- 自動フォールバック戦略
- 自動Redisキャッシュ（24時間TTL）
- 統計情報収集（ソース別ヒット率）

### 2. SQS非同期注文システム

```python
# 注文をSQS経由で非同期処理、Kill Switch確認を統合
await order_publisher.publish_order_request(
    symbol="USDJPY",
    order_type="BUY",
    lots=0.1,
    tp=150.50,
    sl=149.50
)
# → SQS FIFO Queue → ProcessSQSOrderUseCase → MT5
```

**特徴**:
- Kill Switch自動確認
- 注文バリデーション（ロットサイズ、価格レベル）
- DynamoDB監査証跡
- 98%の注文成功率
- エラーハンドリング・リトライ

### 3. リアルタイムポジション管理

```python
# リアルタイムでポジション状況を監視・管理
positions = position_provider.get_open_positions()
profit_loss = position_provider.calculate_total_pl()
# MT5から直接取得、リアルタイム損益計算
```

**特徴**:
- リアルタイムポジション取得（MT5直接接続）
- 損益計算（実現/未実現）
- 手動決済機能
- リスク監視
- 本日損益集計

### 4. Kill Switch（緊急停止機能）

```python
# グローバルな取引停止メカニズム
kill_switch_repo.activate()  # 全注文を即座に停止
# DynamoDBに永続化、全プロセスで共有
```

**特徴**:
- 手動有効化・無効化（Streamlit UI）
- DynamoDB永続化（状態共有）
- 全注文処理で自動確認
- 監査ログ記録
- 理由の記録

### 5. リアルタイムダッシュボード（Streamlit）

**機能**:
- リアルタイム価格チャート（Plotly）
- ポジション一覧・損益表示
- 手動注文実行
- Kill Switch操作
- システムヘルスチェック
- データソース統計

---

## 実装状況

### Phase別進捗

| Phase | 内容 | 期間 | 進捗 | 完了日 | 主要成果物 |
|-------|------|------|------|--------|-----------|
| **Phase 1** | データ収集基盤 | 7日 | 100% | 2025-10-16 | S3保存、Redis統合 |
| **Phase 2** | データ提供層 | 5日 | 100% | 2025-10-18 | 統合プロバイダー、4層フォールバック |
| **Phase 3** | 注文処理・UI | 10日 | 100% | 2026-01-12 | SQS処理、Streamlit UI、Kill Switch |
| **Phase 3.5** | アーキテクチャ改善 | 2-3日 | 📋 準備完了 | - | Position統合、監査証跡完全化 |
| **Phase 4** | シグナル生成 | 9日 | 📋 計画完了 | - | 4種シグナル、投票システム |
| **Phase 5** | バックテスト | 5日 | 📋 計画完了 | - | Backtest Engine、実トレード比較 |

### 実装済み機能

```
✅ Phase 1-3: 100%完了（2026-01-12）
├── MT5接続・データ収集
├── S3保存機能（パーティション設計: symbol/timeframe/year/month/day）
├── Redis統合（15-94ms応答、24時間キャッシュ）
├── データ統合プロバイダー（4ソース統合、自動フォールバック）
├── SQS非同期注文システム（FIFO、順序保証）
├── Kill Switch（DynamoDB永続化、グローバル共有）
├── ポジション管理（リアルタイム取得、損益計算）
├── Streamlit UI（リアルタイムダッシュボード）
├── Domain層統合（Order Entity、Repository Pattern）
└── MT5 Provider 3種（Price/Account/Position）

⏳ Phase 3.5: 準備完了
└── Position管理のクリーンアーキテクチャ統合
    ├── Repository Pattern適用
    ├── SQSフロー統一
    ├── 監査証跡完全化
    └── Kill Switch統合

📋 Phase 4/5: 計画完了
├── Phase 4: シグナル生成
│   └── Jupyterバックテストコード移植（455行）
└── Phase 5: バックテスト
    └── vectorbtエンジン統合、実トレード比較
```

### テストカバレッジ

```
Production Code: ~4,200行（13ファイル）
Test Code:       ~1,800行（8ファイル）
Coverage:        86%

Unit Tests:      73テスト 100%成功
Integration:     設計完了
```

---

## セットアップ

### 前提条件

- Python 3.11+
- AWS アカウント（EC2, ElastiCache, DynamoDB, S3, SQS等）
- MetaTrader 5アカウント

### ローカル開発環境

```bash
# 1. リポジトリクローン
git clone https://github.com/Riki-22/axia-tss.git
cd axia-tss

# 2. 仮想環境作成
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. 依存パッケージインストール
pip install -r requirements.txt

# 4. 環境変数設定
# .env ファイルを作成し、以下を設定
# AWS_REGION=ap-northeast-1
# MT5_LOGIN=your_mt5_login
# MT5_PASSWORD=your_mt5_password
# MT5_SERVER=your_mt5_server
# REDIS_ENDPOINT=your_redis_endpoint

# 5. Streamlit起動
streamlit run src/presentation/ui/streamlit/app.py
```

### 本番環境（EC2 Windows）

```bash
# 1. EC2インスタンスセットアップ（Windows Server 2022）
# - Python 3.11インストール
# - MetaTrader 5インストール
# - AWS認証情報設定

# 2. 依存パッケージインストール
pip install -r requirements.txt

# 3. タスクスケジューラ設定（4プロセス）
# - AXIA_Streamlit: システム起動時
# - AXIA_Order_Manager: システム起動時
# - AXIA_Data_Collector: 毎日 07:00 JST
# - AXIA_MT5: システム起動時

# 4. サービス起動
# タスクスケジューラにより自動起動
```

**注意**: MT5のAutoTrading機能を有効にするには、手動でRDPログインが必要です（プラットフォームの制約）。

---

## プロジェクト構造

```
axia-tss/
├── src/
│   ├── domain/                    # ドメイン層（ビジネスロジック）
│   │   ├── entities/              # Order, Position等
│   │   ├── repositories/          # リポジトリインターフェース
│   │   └── services/              # ドメインサービス
│   │
│   ├── application/               # アプリケーション層（ユースケース）
│   │   └── use_cases/
│   │       ├── data_collection/   # データ収集
│   │       └── order_processing/  # 注文処理
│   │
│   ├── infrastructure/            # インフラ層（技術実装）
│   │   ├── persistence/           # データ永続化
│   │   │   ├── dynamodb/          # DynamoDBリポジトリ
│   │   │   ├── redis/             # Redisリポジトリ
│   │   │   └── s3/                # S3リポジトリ
│   │   ├── gateways/              # 外部連携
│   │   │   ├── brokers/mt5/       # MT5接続
│   │   │   └── market_data/       # データプロバイダー
│   │   └── messaging/             # メッセージング
│   │       └── sqs/               # SQS Publisher
│   │
│   ├── presentation/              # プレゼンテーション層（UI）
│   │   └── ui/streamlit/          # Streamlit UI
│   │
│   └── infrastructure/di/         # 依存性注入
│       └── container.py           # DIコンテナ
│
├── tests/                         # テストコード
│   ├── unit/                      # ユニットテスト（73テスト）
│   └── integration/               # 統合テスト
│
├── docs/                          # ドキュメント（~10,000行）
│   ├── logical_design/            # 論理設計
│   ├── physical_design/           # 物理設計
│   └── implementation/            # 実装管理
│
└── requirements.txt               # Python依存パッケージ
```

### システムレイヤー構成

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                       │
│  Streamlit UI (リアルタイム監視・手動操作・チャート表示)               │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                       Application Layer                         │
│  • Data Collection UseCase  (データ収集オーケストレーション)         │
│  • Order Processing UseCase (注文処理ビジネスロジック)              │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                         Domain Layer                            │
│  • Order Entity (注文ドメインモデル)                               │
│  • Position Entity (ポジションドメインモデル)                       │
│  • Kill Switch (緊急停止メカニズム)                                │
│  • Validators (ビジネスルール検証)                                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                        │
│                                                                 │
│  [Gateways]              [Persistence]           [Messaging]    │
│  • MT5 (取引実行)        • DynamoDB （注文履歴）   • SQS（非同期）   │
│  • OhlcvProvider統合     • Redis （ホットキャッシュ）               │
│    - Redis (15-94ms)    • S3 (コールドストレージ)                  │
│    - MT5                                                        │
│    - S3                                                         │
│    - yfinance                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ドキュメント

### 論理設計

- **[Business Requirements](docs/logical_design/business_requirements.md)** - User stories, KPIs, success metrics
- **[Domain Model](docs/logical_design/domain_model.md)** - Entities, services, aggregates  
- **[Architecture Patterns](docs/logical_design/architecture_patterns.md)** - Clean architecture, DDD implementation
- **[Functional Design](docs/logical_design/functional_design.md)** - Implemented features, flows, integrations
- **[Data Model](docs/logical_design/data_model.md)** - 3-tier data strategy, schemas, optimization
- **[Quality Requirements](docs/logical_design/quality_requirements.md)** - Performance SLAs, measured results

### 物理設計

- **[AWS Architecture](docs/physical_design/aws_architecture.md)** - Services configuration, IAM, security
- **[Database Schema](docs/physical_design/database_schema.md)** - DynamoDB/Redis/S3 detailed design
- **[Infrastructure](docs/physical_design/infrastructure.md)** - EC2, networking, automation
- **[Deployment](docs/physical_design/deployment.md)** - Release procedures, environment management
- **[Monitoring](docs/physical_design/monitoring.md)** - CloudWatch, health checks, alerting
- **[Cost Optimization](docs/physical_design/cost_optimization.md)** - Cost analysis, optimization strategies

### 実装ステータス

- **[Basic Design](docs/basic_design.md)** - Integrated design overview with implementation mapping
- **[Current Status](docs/implementation/current_status.md)** - Live implementation status, metrics, progress
- **[Phase 3.5 Plan](docs/implementation/phase3.5_implementation_plan.md)** - Architecture refinement
- **[Phase 4/5 Plan](docs/implementation/phase4_5_implementation_plan.md)** - Signal generation & backtesting plan

---

## クイックスタート

### For Developers

```bash
# 1. Architecture Understanding (30 min)
Read: docs/basic_design.md → docs/logical_design/architecture_patterns.md

# 2. Implementation Details (45 min)  
Read: docs/logical_design/functional_design.md → docs/logical_design/data_model.md

# 3. Current Status Check (15 min)
Read: docs/implementation/current_status.md
```

### For Infrastructure/DevOps

```bash
# 1. AWS Configuration (30 min)
Read: docs/physical_design/aws_architecture.md → docs/physical_design/infrastructure.md

# 2. Deployment & Operations (30 min)
Read: docs/physical_design/deployment.md → docs/physical_design/monitoring.md

# 3. Cost Management (15 min)
Read: docs/physical_design/cost_optimization.md
```

### For Business/Project Management

```bash  
# 1. Business Context (20 min)
Read: docs/logical_design/business_requirements.md

# 2. Implementation Progress (15 min)
Read: docs/implementation/current_status.md

# 3. System Overview (15 min)
Read: docs/basic_design.md
```

---

## パフォーマンス実測値

| メトリクス | 目標 | 実測値 | 測定日 |
|----------|------|-------|--------|
| **Redis応答時間** | <100ms | 15-94ms | 2025-10-18 |
| **UI描画時間** | <2秒 | 1.2秒 | 2025-10-19 |
| **注文成功率** | >95% | 98% | 2025-10-19 |
| **データ収集成功率** | >95% | 100% (45/45) | 2025-10-16 |
| **メモリ使用量** | <50MB | 8.84MB | 2025-10-18 |

---

## ロードマップ

### 完了済み

- [x] Phase 1: データ収集基盤（2025-10-16完了）
- [x] Phase 2: データ提供層（2025-10-18完了）
- [x] Phase 3: 注文処理・UI（2026-01-12完了）

### 進行中

- [ ] Phase 3.5: アーキテクチャ改善
  - [ ] Position Repository Pattern適用
  - [ ] SQSフロー統一
  - [ ] 監査証跡完全化

### 計画済み

- [ ] Phase 4: シグナル生成
  - [ ] Jupyterテクニカル分析移植
  - [ ] Signal Entity/Service作成
  - [ ] 投票システム実装
  - [ ] シグナル精度評価

- [ ] Phase 5: バックテスト
  - [ ] vectorbtエンジン移植
  - [ ] BacktestUseCase作成
  - [ ] 実トレード vs バックテスト比較

### 将来の拡張

- [ ] **機械学習統合**
  - 市場レジーム検出
  - シグナル最適化
  - パターン認識

- [ ] **本番環境強化**
  - SNSアラート
  - 自動復旧メカニズム
  - パフォーマンス最適化

- [ ] **高度な機能**
  - マルチシンボル対応
  - ポートフォリオ最適化
  - リスク調整ポジションサイジング

---

## セキュリティ

- **AWS Secrets Manager**: 認証情報管理
- **IAM Role**: アクセス制御、最小権限設定
- **VPC**: プライベートサブネット内への配置
- **Security Group**: アクセス元IP制限

---

## コントリビューション

このプロジェクトは個人プロジェクトですが、改善提案やフィードバックを歓迎します。

---

## ライセンス

このプロジェクトは個人利用のみを目的としています。

---

## 謝辞

このプロジェクトは以下の技術・サービスを活用して構築されています：

- **AWS**: フルマネージドインフラ
- **MetaTrader 5**: 取引プラットフォーム
- **Streamlit**: リアルタイムダッシュボード
- **Python**: バックエンド開発言語

---

**Last Updated**: 2026-01-13  
**Version**: 2.0.0  
**Implementation Status**: Phase 1-3: 100% Complete