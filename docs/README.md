# AXIA - Trading Strategy System - ドキュメント

**最終更新**: 2025-10-19  
**実装完了率**: 70%（コア機能）  
**月額運用コスト**: $43.50

---

## システム概要

AXIAは、個人投資家向け自動FX取引システムとして、データ駆動型の意思決定により感情や認知バイアスを排除し、24時間365日の自動取引を通じて持続可能な収益を実現するシステムです。

### 🎯 主要特徴

- **📊 データ統合**: Redis/MT5/S3/yfinanceからの統合データアクセス
- **⚡ 高速処理**: Redis 15-94ms応答、UI描画1.2秒
- **🔒 リスク管理**: Kill Switch、注文バリデーション、楽観的ロック
- **🖥️ リアルタイムUI**: Streamlit による直感的な操作・監視画面
- **☁️ AWS統合**: フルマネージド、月額$43.50の低コスト運用

### 🏗️ アーキテクチャ原則

- **クリーンアーキテクチャ + DDD**: ビジネスロジックと技術詳細の分離
- **3階層データ戦略**: Hot(Redis) / Warm(DynamoDB) / Cold(S3)
- **依存性注入**: テスタビリティとモジュール性の確保
- **段階的実装**: MVP → 機能拡張の着実なアプローチ

---

## 📚 ドキュメント構成

### 🧠 論理設計（Logical Design）

| ドキュメント | 内容 | 実装対応ファイル | 完成度 |
|-------------|------|----------------|-------|
| **[business_requirements.md](logical_design/business_requirements.md)** | ビジネス要件・ユーザーストーリー・KPI | 全システム | ✅ 完了 |
| **[domain_model.md](logical_design/domain_model.md)** | エンティティ・ドメインサービス・集約 | `src/domain/` | ✅ 完了 |
| **[architecture_patterns.md](logical_design/architecture_patterns.md)** | クリーンアーキテクチャ・DDD適用 | `src/infrastructure/di/container.py` | ✅ 完了 |
| **[functional_design.md](logical_design/functional_design.md)** | 実装済み機能・フロー・連携 | `src/application/`, `src/presentation/` | ✅ 完了 |
| **[data_model.md](logical_design/data_model.md)** | データフロー・スキーマ・最適化 | `src/infrastructure/persistence/` | ✅ 完了 |
| **[quality_requirements.md](logical_design/quality_requirements.md)** | 品質要件・実測値・目標 | 全システム | ✅ 完了 |

### 🏗️ 物理設計（Physical Design）

| ドキュメント | 内容 | 実装対応 | 完成度 |
|-------------|------|---------|-------|
| **[aws_architecture.md](physical_design/aws_architecture.md)** | AWS構成・IAM・セキュリティ | 全AWSサービス | ✅ 完了 |
| **[database_schema.md](physical_design/database_schema.md)** | DynamoDB/Redis/S3詳細設計 | 実装済みスキーマ | ✅ 完了 |
| **[infrastructure.md](physical_design/infrastructure.md)** | EC2・ネットワーク・プロセス管理 | EC2設定、Task Scheduler | ✅ 完了 |
| **[deployment.md](physical_design/deployment.md)** | デプロイ手順・環境管理 | PowerShellスクリプト | ✅ 完了 |
| **[monitoring.md](physical_design/monitoring.md)** | 監視・アラート・ログ設計 | CloudWatch、ヘルスチェック | ✅ 完了 |
| **[cost_optimization.md](physical_design/cost_optimization.md)** | コスト分析・最適化戦略 | AWS課金最適化 | ✅ 完了 |

### 📋 統合・管理文書

| ドキュメント | 内容 | 用途 | 更新頻度 |
|-------------|------|------|---------|
| **[basic_design.md](basic_design.md)** | 統合設計書・ディレクトリ構造・実装マッピング | 開発者向け全体把握 | 機能追加時 |
| **[current_status.md](implementation/current_status.md)** | 現在実装状況・実測値・進捗 | プロジェクト管理・レビュー | 週次 |

### 📈 実装計画（Implementation）

| ドキュメント | 対象期間 | 実装状況 | 備考 |
|-------------|---------|---------|------|
| **[implementation_plan.md](implementation/implementation_plan.md)** | Phase 1初期 | ✅ 完了 | 基盤実装完了 |
| **[implementation_plan_v2.md](implementation/implementation_plan_v2.md)** | Week 1-2 | ✅ 完了 | データ統合完了 |
| **[implementation_plan_v3.md](implementation/implementation_plan_v3.md)** | Week 3-4 | 🔄 実行中 | 注文機能完成予定 |

---

## 🚀 クイックスタート

### 設計理解のための推奨読書順序

#### 🔰 初回理解（30分）
1. **[basic_design.md](basic_design.md)** - システム全体像・実装状況把握
2. **[current_status.md](implementation/current_status.md)** - 現在の進捗・実測値確認
3. **[business_requirements.md](logical_design/business_requirements.md)** - システム目的・価値理解

#### 🛠️ 開発者向け（60分）
1. **[architecture_patterns.md](logical_design/architecture_patterns.md)** - 設計原則・パターン理解
2. **[functional_design.md](logical_design/functional_design.md)** - 実装済み機能詳細
3. **[data_model.md](logical_design/data_model.md)** - データフロー・統合戦略

#### ☁️ インフラ管理者向け（45分）
1. **[aws_architecture.md](physical_design/aws_architecture.md)** - AWS構成・設定詳細
2. **[infrastructure.md](physical_design/infrastructure.md)** - EC2・ネットワーク設計
3. **[monitoring.md](physical_design/monitoring.md)** - 監視・アラート設定

### 実装状況クイックリファレンス

| 確認したい情報 | 参照ドキュメント |
|--------------|----------------|
| **現在何が動いているか** | [current_status.md](implementation/current_status.md#1-実装状況概要) |
| **コストがいくらかかるか** | [cost_optimization.md](physical_design/cost_optimization.md#2-現在のコスト構造) |
| **どのAWSサービスを使用中か** | [aws_architecture.md](physical_design/aws_architecture.md#12-サービス利用状況) |
| **実装済み機能は何か** | [functional_design.md](logical_design/functional_design.md#2-実装済み機能) |
| **パフォーマンスはどうか** | [quality_requirements.md](logical_design/quality_requirements.md#21-応答時間要件) |
| **次に実装する機能は** | [current_status.md](implementation/current_status.md#71-week-3残り作業) |

---

## 🔗 外部リンク

### プロジェクト管理
- **GitHub Repository**: [axia-tss](https://github.com/username/axia-tss)
- **AWS Console**: [ap-northeast-1](https://ap-northeast-1.console.aws.amazon.com/)
- **EC2 Instance**: [Streamlit UI](http://ec2-xxx.ap-northeast-1.compute.amazonaws.com:8501)

### 開発ツール
- **Local Development**: Python 3.11 + 仮想環境
- **Testing**: pytest + coverage
- **Deployment**: PowerShell + Task Scheduler
- **Monitoring**: CloudWatch + Streamlit Dashboard

---

## 📝 貢献・フィードバック

### ドキュメント更新ガイドライン

1. **実装完了時**: 対応する設計ドキュメントを更新
2. **新機能追加時**: functional_design.md に詳細を追加
3. **AWS設定変更時**: 関連physical_designドキュメントを更新
4. **パフォーマンス変化時**: quality_requirements.md の実測値更新

### 問題報告

技術的問題や設計上の疑問は、関連するGitHubイシューまたはドキュメントコメントで報告してください。

---

## 📊 ドキュメント統計

### 作成ドキュメント数
- **論理設計**: 6ファイル
- **物理設計**: 6ファイル  
- **実装管理**: 4ファイル
- **アーカイブ**: 11ファイル
- **総計**: 27ファイル

### ドキュメント品質
- **相互リンク率**: 95%
- **実装カバレッジ**: 90%
- **実測値記載率**: 80%
- **更新頻度**: 週次（実装フェーズ）

---

**Document Version**: 3.0  
**Created**: 2025-09-14  
**Updated**: 2025-10-19  
**Type**: ドキュメント総合案内