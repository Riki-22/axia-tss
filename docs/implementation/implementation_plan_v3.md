# 📋 AXIA Week 3 実装計画書

**作成日**: 2025年10月18日  
**実装期間**: 2025年10月19日（土）〜 10月21日（月）  
**目標**: 注文機能完全実装 + リアルタイムデータ対応

---

## 🎯 Week 3の目標

```
優先度★★★（必須）:
1. ✅ 注文機能の完全実装（Day 1完了）
   - SQS order_publisher実装
   - Streamlit → SQS → order_manager → MT5の完全連携
   - 注文結果のリアルタイム表示

2. ✅ リアルタイムデータ対応（Day 2完了）
   - OhlcvDataProvider統合
   - Redis鮮度メタデータ機能
   - データ鮮度の可視化
   - 手動更新機能（🔄最新ボタン）

3. ⏳ Windows EC2デプロイ（Day 3進行中）
   - EC2スケールアップ（t3.micro → t3.small）✅
   - セキュリティグループ設定 ✅
   - Streamlit起動確認 ✅
   - タスクスケジューラ設定 ⏳
   - 4プロセス自動起動 ⏳
   - 統合動作確認 ⏳
```

---

## 📅 3日間スケジュール（実績版）

### **Day 1（土）: 注文機能実装（8時間）** ✅ 完了

```
午前（4時間）: SQS注文送信 ✅
  ├─ order_publisher.py実装（2時間）✅
  ├─ DIコンテナ更新（30分）✅
  └─ ローカルテスト（1.5時間）✅

午後（4時間）: Streamlit注文UI ✅
  ├─ trading_page.py更新（3時間）✅
  │  ├─ 注文パネル拡張
  │  ├─ BUY/SELLボタン実装
  │  └─ SQS送信処理
  └─ ローカル統合テスト（1時間）✅

実装成果:
✅ SQSOrderPublisher実装（MOCK対応）
✅ 注文パネルUI完全実装
✅ BUY/SELL注文送信成功（MOCKモード）
```

### **Day 2（日）: リアルタイムデータ対応（8時間）** ✅ 完了

```
午前（4時間）: Redis鮮度メタデータ ✅
  ├─ RedisOhlcvDataRepository拡張（2時間）✅
  │  ├─ save_ohlcv_with_metadata実装
  │  └─ load_ohlcv_with_metadata実装
  └─ OhlcvDataProvider鮮度チェック（2時間）✅
     ├─ _get_max_age実装
     └─ 鮮度判定ロジック

午後（4時間）: Streamlit UI更新 ✅
  ├─ chart_data_source.py統合（2時間）✅
  │  ├─ OhlcvDataProvider利用
  │  └─ force_refresh実装
  ├─ price_chart.py修正（1時間）✅
  │  └─ Day 2対応版に更新
  └─ yfinance統合修正（1時間）✅
     └─ _fetch_from_yfinance実装

実装成果:
✅ Redis鮮度メタデータ機能
✅ OhlcvDataProvider鮮度チェック
✅ chart_data_source.py完全書き換え
✅ price_chart.py Day 2対応
✅ yfinance統合完了
✅ チャート表示成功（ローカル + EC2）
✅ Redisキャッシュヒット成功（0.015s〜0.094s）
```

### **Day 3（月）: EC2デプロイ + 現在価格実装** ✅ 100%完了

#### **午前（4時間）: Windows EC2構築** ✅ 100%完了

```
✅ RDP接続・環境確認

**EC2パブリックIP取得**
```powershell
# PowerShellで実行
$publicIP = (Invoke-WebRequest -Uri http://169.254.169.254/latest/meta-data/public-ipv4 -UseBasicParsing).Content
Write-Host "`nAccess URL: http://${publicIP}:8501`n" -ForegroundColor Green
```

✅ EC2スケールアップ（t3.small）
✅ Git Pull + 依存関係更新
✅ セキュリティグループ設定
✅ Streamlit起動確認
✅ バグ修正（4件）
```

#### **午後（4.5時間）: 現在価格 + 口座情報実装** ✅ 100%完了

```
13:00-14:00（1時間）: MT5価格取得プロバイダー実装 ✅
  ✅ MT5PriceProvider作成（290行）
  │  ✅ get_current_price(symbol) → dict
  │  ✅ get_bid_ask(symbol) → tuple
  │  ✅ get_symbol_info(symbol) → dict
  ✅ DIContainer統合

14:00-15:30（1.5時間）: MT5口座情報プロバイダー実装 ✅
  ✅ MT5AccountProvider作成（320行）
  │  ✅ get_account_info() → dict
  │  ✅ get_balance() → float
  │  ✅ get_margin_info() → dict
  │  ✅ calculate_today_pl() → dict（NYクローズ基準）
  ✅ DIContainer統合

15:30-17:00（1.5時間）: ヘッダーメトリクス + 注文機能実装 ✅
  ✅ header.py更新（60行）
  │  ✅ MT5AccountProvider呼び出し
  │  ✅ リアルタイム表示
  │  ✅ エラーハンドリング
  │  ✅ 証拠金率表示（inf%対応）
  ✅ trading_page.py現在価格更新
     ✅ MT5PriceProvider呼び出し
     ✅ _execute_order()修正

17:00-17:30（30分）: ドキュメント更新 ✅
  ✅ architecture_patterns.md更新（命名規則追加）
  ✅ basic_design.md更新（MT5ファイル一覧）
  ✅ implementation_plan_v3.md更新（本ファイル）
  ✅ current_status.md更新（実装状況）
```

**実装ファイル**:
- ✅ `src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py`（新規、290行）
- ✅ `src/infrastructure/gateways/brokers/mt5/mt5_account_provider.py`（新規、320行）
- ✅ `src/infrastructure/di/container.py`（更新、+45行）
- ✅ `src/presentation/ui/streamlit/layouts/header.py`（更新、+60行）
- ✅ `src/presentation/ui/streamlit/pages/trading_page.py`（更新、_execute_order修正）

**ドキュメント更新**:
- ✅ `docs/logical_design/architecture_patterns.md`（Section 9追加）
- ✅ `docs/basic_design.md`（MT5関連セクション更新）
- ✅ `docs/implementation/implementation_plan_v3.md`（本ファイル）
- ✅ `docs/implementation/current_status.md`（実装状況更新）

**動作確認（EC2実機テスト）**:
- ✅ MT5PriceProvider: USDJPY 150.646（spread 27.0 pips）
- ✅ MT5AccountProvider: Balance 1,002,312 JPY
- ✅ 本日損益計算: NYクローズ基準（2025-10-18 21:00 UTC）
- ✅ ヘッダーメトリクス: リアルタイム表示
- ✅ 現在価格ベース注文: SQS送信成功（MessageId取得）
- ✅ 証拠金率表示: ポジションなし対応

**パフォーマンス**:
- Provider初期化: <1秒
- 価格取得: <100ms
- 口座情報取得: <100ms
- SQS注文送信: <1秒
## 🚀 次のステップ（Week 4以降）

### Week 4: ポートフォリオ準備

```
1. README.md充実
2. スクリーンショット作成
3. デモ動画録画
4. GitHub Public化
5. セキュリティ最終チェック
```

### Phase 3: 高度化

```
1. S3並列読み込み
2. バックテスト機能
3. パフォーマンス分析
4. MLモデル統合
```
