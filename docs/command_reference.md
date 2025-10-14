# AXIA プロジェクト共通コマンド集

## Overview

本ドキュメントは、AXIA開発・運用における頻出コマンドを目的別にまとめたものです。インフラ構築、デプロイ、テスト、監視、分析など、各フェーズに対応する標準的なCLI操作を網羅します。

**Last Updated**: 2025-07-31  
**Version**: 1.0

---

## 1. 環境構築・初期化

```bash
# 仮想環境の作成と有効化
# python -m venv .venv
# source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

# 必要パッケージのインストール
# pip install -r requirements.txt
# pip install -r requirements-dev.txt
# dotenv ファイルの初期生成
# cp .env.example .env

# source /opt/homebrew/anaconda3/bin/activate base

# 既存環境を更新
conda activate axia-env
conda install -c conda-forge streamlit redis-py python-dotenv watchdog

# 環境を再構築（クリーンな状態から）
conda env remove -n axia-env
conda env create -f environment.yml
conda activate axia-env

# 仮想環境の有効化
conda activate axia-env
```

## 2. テスト関連

```bash
# API Gatewayへのメッセージ送信
curl -X POST \
     -H "Content-Type: application/json" \
     -d @./tests/unit/payload/test_market-oco.json \
     https://nytm3lpkoj.execute-api.ap-northeast-1.amazonaws.com/webhook
```

```bash
# ユニットテストの実行
pytest tests/unit/

# 統合テストの実行
pytest tests/integration/

# カバレッジ付きで全体テスト
pytest --cov=src --cov-report=term-missing

# テスト + フォーマッタチェック一括（Makefile化推奨）
make test
```

## 3. Lint / Format チェック

```bash
# フォーマット修正（black）
black src/ tests/

# インポート整形（isort）
isort src/ tests/

# 静的解析（flake8）
flake8 src/ tests/

# 型チェック（mypy）
mypy src/
```

## 4. AWS 関連

```bash
# IAM Identity Center経由で一時認証情報を取得
aws sso login --profile dev-sso

# 取得した認証情報が正しいか確認
aws sts get-caller-identity --profile dev-sso
```

```bash
# SAMビルド
sam build

# SAMローカルテスト（イベントシミュレーション）
sam local invoke "FunctionName" -e events/sample_event.json

# SAMデプロイ（プロンプト省略、IAM付き）
sam deploy --stack-name axia-backend \
  --region ap-northeast-1 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset
```

## 5. DynamoDB操作（AWS CLI）

```bash
# テーブルスキャン（全件取得）
aws dynamodb scan --table-name TSS_DynamoDB_OrderState

# 指定キーで検索
aws dynamodb get-item --table-name TSS_DynamoDB_OrderState \
  --key '{"pk": {"S": "ORDER#12345"}, "sk": {"S": "METADATA"}}'

# テーブル作成（JSONファイル指定）
aws dynamodb create-table --cli-input-json file://configs/dynamodb_table.json
```

## 6. MT5接続・デバッグ（Python）

```bash
# MT5接続確認
import MetaTrader5 as mt5
mt5.initialize()
print(mt5.terminal_info())
```

## 7. データ取得・分析スクリプト

```bash
# 過去チャートデータの収集（例: yfinance）
python scripts/fetch_historical_data.py --symbol USDJPY --interval 1h --days 90

# バックテスト実行
python scripts/run_backtest.py --config configs/backtest_sample.yaml

# モデル推論テスト（MLOps系）
python scripts/predict_weights.py --input data/sample_signals.json
```

## 8. Git操作（共通運用）

```bash
# ブランチ作成
git checkout -b feature/add-new-signal

# 最新main取り込み
git fetch origin
git merge origin/main

# PR作成用push
git push origin feature/add-new-signal
```

## 9. SAM インフラデプロイ

### 実行前確認
```bash
# 現在の認証情報確認
aws sts get-caller-identity --profile dev-sso

# 期待される出力: Account = 837692470023

# リージョン確認
aws configure get region
# 期待される出力: ap-northeast-1

# SAM形式テンプレートの検証
sam validate --template-file application.yaml --profile dev-sso

# 期待される出力:
# application.yaml is a valid SAM Template
```

### SAM Build

```bash
# SAMビルド実行（テンプレート検証）
sam build --template-file application.yaml --profile dev-sso

# 成功時の出力例:
# Build Succeeded
# Built Artifacts  : .aws-sam/build
```

### SAM Deploy

#### 3-1. 初回デプロイ（対話モード）
```bash
sam deploy \
  --template-file application.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1 \
  --guided \
  --profile dev-sso

# 対話プロンプトでの推奨設定:
# Stack Name: axia-trading-system
# AWS Region: ap-northeast-1
# Confirm changes before deploy: Yes
# Allow SAM CLI IAM role creation: Yes
# Disable rollback: No
# Save arguments to configuration file: Yes
# Configuration file name: samconfig.toml
```

#### 3-2. 変更セット確認
デプロイ前に、以下のような変更セットが表示：

```
CloudFormation stack changeset
---------------------------------
Operation                     LogicalResourceId              ResourceType
---------------------------------
+ Add                         ElastiCacheSubnetGroup         AWS::ElastiCache::SubnetGroup
+ Add                         RedisSecurityGroup             AWS::EC2::SecurityGroup
+ Add                         TSSRedisCluster                AWS::ElastiCache::CacheCluster
+ Add                         RedisEndpointParameter         AWS::SSM::Parameter
+ Add                         RedisPortParameter             AWS::SSM::Parameter
* Modify                      IAMRoleTSSEC2Role              AWS::IAM::Role
---------------------------------
```

#### 3-3. デプロイ実行確認
```
Deploy this changeset? [y/N]: y
```

#### 3-4. デプロイ進行確認
```bash
# 別ターミナルでスタック状態監視
watch -n 5 'aws cloudformation describe-stacks \
  --stack-name axia-trading-system \
  --query "Stacks[0].StackStatus" \
  --output text'

# 期待される状態遷移:
# UPDATE_IN_PROGRESS → UPDATE_COMPLETE_CLEANUP_IN_PROGRESS → UPDATE_COMPLETE
```

**⏱️ 所要時間**: 約12-15分（ElastiCacheクラスタ作成時間）

### デプロイ検証

#### 4-1. スタック状態確認
```bash
aws cloudformation describe-stacks \
  --stack-name axia-trading-system \
  --query "Stacks[0].[StackStatus, LastUpdatedTime]" \
  --output table

# 期待される出力:
# StackStatus: UPDATE_COMPLETE
```

#### 4-2. Redis情報取得
```bash
# Redis Endpoint取得
aws cloudformation describe-stacks \
  --stack-name axia-trading-system \
  --query "Stacks[0].Outputs[?OutputKey=='RedisEndpoint'].OutputValue" \
  --output text

# 出力例: tss-market-data-cache.abc123.0001.apne1.cache.amazonaws.com

# Redis Port取得
aws cloudformation describe-stacks \
  --stack-name axia-trading-system \
  --query "Stacks[0].Outputs[?OutputKey=='RedisPort'].OutputValue" \
  --output text

# 出力例: 6379
```

#### 4-3. Parameter Store確認
```bash
# Parameter Store に保存された接続情報確認
aws ssm get-parameter --name "/tss/redis/endpoint" --query "Parameter.Value" --output text
aws ssm get-parameter --name "/tss/redis/port" --query "Parameter.Value" --output text
```

#### 4-4. Redis クラスタ状態確認
```bash
aws elasticache describe-cache-clusters \
  --cache-cluster-id tss-market-data-cache \
  --show-cache-node-info \
  --query "CacheClusters[0].[CacheClusterStatus, CacheNodeType, EngineVersion]" \
  --output table

# 期待される出力:
# Status: available
# NodeType: cache.t4g.micro
# EngineVersion: 7.1
```

### デプロイロールバック発生時
```bash
# スタックイベント確認
aws cloudformation describe-stack-events \
  --stack-name axia-trading-system \
  --max-items 20 \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED']"

# 問題解決後、再デプロイ
sam deploy --template-file application.yaml --stack-name axia-trading-system
```

---