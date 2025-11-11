# AXIA Trading Strategy System - コード規模分析レポート

生成日: 2025-11-12
プロジェクト: AXIA Trading Strategy System (AXIA-TSS)

---

## 1. プロジェクト概要

- **プロジェクト名**: AXIA Trading Strategy System (AXIA-TSS)
- **アーキテクチャ**: Clean Architecture + Domain-Driven Design (DDD)
- **言語**: Python 3.11+
- **テストフレームワーク**: pytest
- **AWS統合**: S3, DynamoDB, SQS, Lambda, CloudWatch

---

## 2. コード規模サマリー

| 項目 | ファイル数 | 総行数 | 実コード | コメント | 空行 |
|------|-----------|--------|---------|---------|------|
| **ソースコード (src/)** | 93 | 12,801 | 7,172 | 3,460 | 2,169 |
| **テストコード (tests/)** | 62 | 14,127 | 6,828 | 4,573 | 2,726 |
| **合計** | **155** | **26,928** | **14,000** | **8,033** | **4,895** |

---

## 3. コード比率

- **テスト/ソースコード比率**: 95.2% (テスト: 6,828行 / ソース: 7,172行) ✅
- **コメント率**: 29.8% (8,033行 / 26,928行) ✅
- **実コード率**: 52.0% (14,000行 / 26,928行)

---

## 4. レイヤー別統計 (ソースコード)

| レイヤー | ファイル数 | 実コード行数 | 割合 |
|---------|-----------|-------------|------|
| **Infrastructure** | 40 | 3,832 | 53.4% |
| **Presentation** | 28 | 2,068 | 28.8% |
| **Domain** | 19 | 1,006 | 14.0% |
| **Application** | 6 | 266 | 3.7% |
| **合計** | **93** | **7,172** | **100.0%** |

---

## 5. 詳細モジュール別統計 (Top 10)

| モジュール | ファイル | 実コード |
|-----------|---------|---------|
| presentation/ui | 24 | 1,944 |
| infrastructure/gateways | 17 | 1,792 |
| infrastructure/persistence | 11 | 1,383 |
| domain/services | 10 | 622 |
| infrastructure/config | 7 | 337 |
| application/use_cases | 5 | 266 |
| domain/repositories | 5 | 204 |
| domain/entities | 3 | 180 |
| infrastructure/di | 2 | 176 |
| presentation/cli | 3 | 124 |

---

## 6. テストコード統計

| テスト種別 | ファイル | 実コード |
|-----------|---------|---------|
| 単体テスト (infrastructure/gateways) | 19 | 2,674 |
| 単体テスト (infrastructure/persistence) | 15 | 1,945 |
| 単体テスト (domain/services) | 8 | 877 |
| **統合テスト (integration)** | **4** | **446** |
| 単体テスト (domain/entities) | 3 | 348 |
| 単体テスト (application/use_cases) | 5 | 338 |
| 単体テスト (infrastructure/di) | 2 | 197 |
| **合計** | **62** | **6,828** |

---

## 7. テストカバレッジ

### テスト総数: 481テスト (100%成功)

- **単体テスト**: 462テスト (95.9%)
- **統合テスト**: 19テスト (4.1%)

### 実行時間: 1.84秒 (高速)

### 統合テスト内訳:
- **Data Collection Flow** (6テスト)
  - Redis → MT5 フォールバック
  - MT5 → S3 フォールバック
  - キャッシュヒット検証
  - 全ソース失敗ハンドリング
  - ソース優先順位マトリックス

- **Kill Switch Scenario** (7テスト)
  - ON/OFF切り替えフロー
  - 安全側フェイルオーバー
  - エラー時のデフォルト動作

- **Multi-Source Fallback** (6テスト)
  - 3段階フォールバック
  - 例外発生時の継続
  - 統計情報蓄積

---

## 8. ファイル種別統計

| ファイル種別 | ファイル数 |
|-------------|-----------|
| Python (.py) | 155 |
| HTML (.html) | 95 |
| Markdown (.md) | 35 |
| JSON (.json) | 8 |
| PNG画像 (.png) | 7 |
| PowerShell (.ps1) | 6 |
| Shell Script (.sh) | 3 |
| YAML (.yaml, .yml) | 3 |
| その他 | 11 |

---

## 9. Clean Architecture レイヤー構造

```
┌─────────────────────────────────────────────────────────────┐
│                  Presentation Layer                         │
│     (UI/CLI - 28 files, 2,068 LOC)                         │
│  • Streamlit UI (24 files)                                 │
│  • CLI Interface (3 files)                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓ (依存)
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                          │
│     (Use Cases - 6 files, 266 LOC)                         │
│  • Data Collection Use Cases                               │
│  • Order Processing Use Cases                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓ (依存)
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                             │
│     (Entities/Services - 19 files, 1,006 LOC)              │
│  • Entities: Order, Position, OHLCV (3 files)             │
│  • Services: Technical Indicators (10 files)               │
│  • Repositories: Interfaces (5 files)                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↑ (実装)
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                         │
│     (Gateways/Persistence - 40 files, 3,832 LOC)           │
│  • Gateways: MT5, Messaging (17 files)                     │
│  • Persistence: S3, Redis, DynamoDB (11 files)             │
│  • Config: Settings, Logging (7 files)                     │
│  • DI: Dependency Injection (2 files)                      │
│  • Monitoring: Metrics, Alerts (1 file)                    │
│  • Serverless: Lambda Handlers (1 file)                    │
└─────────────────────────────────────────────────────────────┘
```

### 依存関係の方向
- Presentation → Application → Domain
- Infrastructure → Domain (インターフェース実装)

---

## 10. 主要コンポーネント詳細

### Infrastructure Layer
- **Gateways** (17 files, 1,792 LOC)
  - MT5 Broker Gateway: リアルタイム取引
  - Market Data Provider: マルチソースデータ統合
  - SQS Messaging: 非同期メッセージング

- **Persistence** (11 files, 1,383 LOC)
  - S3 Repository: 長期履歴データ保存
  - Redis Repository: リアルタイムキャッシュ
  - DynamoDB Repository: 状態管理・Kill Switch

- **Config** (7 files, 337 LOC)
  - Settings: 環境設定管理
  - Logging: 構造化ログ

### Domain Layer
- **Entities** (3 files, 180 LOC)
  - Order: 注文エンティティ
  - Position: ポジションエンティティ
  - OHLCV: 市場データエンティティ

- **Services** (10 files, 622 LOC)
  - Technical Indicators: 50+ インジケーター

- **Repositories** (5 files, 204 LOC)
  - Interface定義のみ（実装はInfrastructure）

### Presentation Layer
- **Streamlit UI** (24 files, 1,944 LOC)
  - ダッシュボード
  - チャート表示
  - トレード管理
  - モニタリング

- **CLI** (3 files, 124 LOC)
  - コマンドライン操作

---

## 11. テスト品質指標

### 単体テスト (Unit Tests)
- **総数**: 462テスト
- **ファイル数**: 56ファイル
- **実コード**: 6,379 LOC

#### Infrastructure Tests (36 files, 4,816 LOC)
- Gateways Tests (19 files, 2,674 LOC)
  - MT5 Broker Gateway: 接続、注文処理、例外ハンドリング
  - Market Data Provider: データ取得、フォールバック
  - SQS Messaging: メッセージ送受信、エラー処理

- Persistence Tests (15 files, 1,945 LOC)
  - S3 Repository: CRUD操作、例外ハンドリング
  - Redis Repository: キャッシュ操作、TTL管理
  - DynamoDB Repository: Kill Switch、状態管理

- DI Tests (2 files, 197 LOC)
  - Dependency Injection: コンテナ、ライフサイクル

#### Domain Tests (12 files, 1,425 LOC)
- Services Tests (8 files, 877 LOC)
  - Technical Indicators: 50+ インジケーター検証

- Entities Tests (3 files, 348 LOC)
  - Order: バリデーション、ビジネスルール
  - Position: 状態遷移、計算ロジック
  - OHLCV: データ整合性

#### Application Tests (6 files, 338 LOC)
- Use Cases Tests (5 files, 338 LOC)
  - Data Collection: データ収集フロー
  - Order Processing: 注文処理フロー

### 統合テスト (Integration Tests)
- **総数**: 19テスト
- **ファイル数**: 4ファイル
- **実コード**: 446 LOC

---

## 12. コード品質評価総括

### ✅ Clean Architecture準拠
- レイヤー分離が明確
- 依存関係の方向が正しい
- インターフェース/実装分離

### ✅ Domain-Driven Design (DDD)
- エンティティ: Order, Position, OHLCV
- ドメインサービス: Technical Indicators
- リポジトリパターン適用

### ✅ テスト駆動開発 (TDD)
- テスト/ソース比率: 95.2%
- 単体テスト: 462テスト
- 統合テスト: 19テスト
- テスト成功率: 100%

### ✅ 例外ハンドリング
- 包括的な例外テスト
- フェイルセーフ機構
- エラーログ記録

### ✅ Production Ready
- AWS統合: S3, DynamoDB, SQS, Lambda
- 監視・アラート: CloudWatch
- Kill Switch機能
- マルチソースフォールバック

---

## 13. プロジェクト規模評価

### コード規模: 中規模 (14,000 LOC)
- 小規模: < 5,000行
- **中規模: 5,000 ~ 50,000行** ✅
- 大規模: > 50,000行

### 品質レベル: Production Ready ⭐⭐⭐⭐⭐

### 保守性: 優秀
- Clean Architecture + 高テストカバレッジ
- 包括的なドキュメント
- コメント率29.8%

---

## 14. 統計サマリー

| 指標 | 値 | 評価 |
|------|-----|------|
| 総Pythonファイル数 | 155 | ✅ |
| 総行数 | 26,928 | ✅ |
| 実コード行数 | 14,000 | ✅ 中規模 |
| テスト総数 | 481 | ✅ |
| テスト成功率 | 100% | ✅ 完璧 |
| テスト/ソース比率 | 95.2% | ✅ 優秀 |
| コメント率 | 29.8% | ✅ 適切 |
| 実行時間 | 1.84秒 | ✅ 高速 |

---

**生成ツール**: カスタムPythonスクリプト
**分析対象**: src/, tests/
**除外対象**: .venv/, venv/, __pycache__/, .git/
