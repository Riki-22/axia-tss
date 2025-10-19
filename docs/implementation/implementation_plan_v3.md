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

### **Day 3（月）: EC2デプロイ + 動作確認（8時間）** ⏳ 進行中

```
午前（4時間）: Windows EC2構築 ✅ 70%完了
  ├─ RDP接続・環境確認（30分）✅
  ├─ EC2スケールアップ（30分）✅
  │  └─ t3.micro → t3.small（2GB RAM）
  ├─ Git Pull + 依存関係更新（1時間）✅
  ├─ セキュリティグループ設定（1時間）✅
  │  ├─ ポート8501開放
  │  └─ Windowsファイアウォール設定
  └─ Streamlit起動確認（1時間）✅
     ├─ Redis接続成功
     ├─ MT5認証成功
     └─ チャート描画成功

午後（4時間）: タスクスケジューラ + 統合テスト ⏳ 0%
  ├─ ブラウザアクセス確認（30分）⏳
  ├─ タスクスケジューラ設定（2時間）⏳
  │  ├─ order_manager自動起動
  │  ├─ data_collector日次実行
  │  ├─ Streamlit自動起動
  │  └─ MT5自動起動
  └─ 統合テスト（1.5時間）⏳
     ├─ 4プロセス同時起動
     ├─ メモリ使用量測定
     ├─ BUY/SELL注文テスト
     └─ 最終確認
```

---

## 🔧 Day 3 午後: 残り実装内容

### Step 1: ブラウザアクセス確認（30分）

**目的**: 外部からStreamlitにアクセスできることを確認

#### 実施内容:

1. **EC2パブリックIP取得**
```powershell
# PowerShellで実行
$publicIP = (Invoke-WebRequest -Uri http://169.254.169.254/latest/meta-data/public-ipv4 -UseBasicParsing).Content
Write-Host "`nAccess URL: http://${publicIP}:8501`n" -ForegroundColor Green
```

2. **ブラウザでアクセス**
   - URL: `http://<パブリックIP>:8501`
   - 確認項目:
     - ✅ チャート表示
     - ✅ 通貨ペア選択動作
     - ✅ 時間足選択動作
     - ✅ 注文パネル表示
     - ✅ データ鮮度表示

3. **スクリーンショット取得**
   - チャート表示画面
   - 注文パネル画面

---

### Step 2: タスクスケジューラ設定（2時間）

**目的**: 4プロセスの自動起動設定

#### 2-1. order_manager自動起動（30分）

```xml
名前: AXIA_Order_Manager
説明: SQS注文処理サービス
トリガー: システム起動時
アクション:
  プログラム: C:\Users\Administrator\Projects\axia-tss\.venv\Scripts\python.exe
  引数: C:\Users\Administrator\Projects\axia-tss\src\presentation\cli\run_order_processor.py
  開始フォルダ: C:\Users\Administrator\Projects\axia-tss
設定:
  ✅ 最高の特権で実行
  ✅ ユーザーがログオンしているかどうかにかかわらず実行
  ✅ タスクの実行時間制限: 無効
  ✅ タスク失敗時: 10分後に再起動（最大3回）
  ✅ 実行中のタスクを停止するまでの時間: なし
```

**PowerShellコマンド:**
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\Administrator\Projects\axia-tss\.venv\Scripts\python.exe" -Argument "C:\Users\Administrator\Projects\axia-tss\src\presentation\cli\run_order_processor.py" -WorkingDirectory "C:\Users\Administrator\Projects\axia-tss"

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName "AXIA_Order_Manager" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "AXIA Order Manager Service"
```

#### 2-2. data_collector日次実行（30分）

```xml
名前: AXIA_Data_Collector
説明: 日次データ収集（NYクローズ後）
トリガー: 毎日 JST 07:00（冬時間）/ 06:00（夏時間）
アクション:
  プログラム: C:\Users\Administrator\Projects\axia-tss\.venv\Scripts\python.exe
  引数: C:\Users\Administrator\Projects\axia-tss\src\presentation\cli\run_data_collector.py
  開始フォルダ: C:\Users\Administrator\Projects\axia-tss
設定:
  ✅ 最高の特権で実行
  ✅ タスク失敗時: 5分後に再起動（最大2回）
  ✅ 実行時間制限: 1時間
```

**PowerShellコマンド:**
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\Administrator\Projects\axia-tss\.venv\Scripts\python.exe" -Argument "C:\Users\Administrator\Projects\axia-tss\src\presentation\cli\run_data_collector.py" -WorkingDirectory "C:\Users\Administrator\Projects\axia-tss"

$trigger = New-ScheduledTaskTrigger -Daily -At "07:00"

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName "AXIA_Data_Collector" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "AXIA Daily Data Collection"
```

#### 2-3. Streamlit自動起動（30分）

```xml
名前: AXIA_Streamlit
説明: Streamlit UIサービス
トリガー: システム起動時（5分遅延）
アクション:
  プログラム: C:\Users\Administrator\Projects\axia-tss\.venv\Scripts\streamlit.exe
  引数: run C:\Users\Administrator\Projects\axia-tss\src\presentation\ui\streamlit\app.py --server.port=8501 --server.address=0.0.0.0
  開始フォルダ: C:\Users\Administrator\Projects\axia-tss
設定:
  ✅ 最高の特権で実行
  ✅ ユーザーがログオンしているかどうかにかかわらず実行
  ✅ タスクの実行時間制限: 無効
  ✅ 起動遅延: 5分（他サービスの起動完了を待つ）
```

**PowerShellコマンド:**
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\Administrator\Projects\axia-tss\.venv\Scripts\streamlit.exe" -Argument "run C:\Users\Administrator\Projects\axia-tss\src\presentation\ui\streamlit\app.py --server.port=8501 --server.address=0.0.0.0" -WorkingDirectory "C:\Users\Administrator\Projects\axia-tss"

$trigger = New-ScheduledTaskTrigger -AtStartup
# 5分遅延を追加
$trigger.Delay = "PT5M"

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName "AXIA_Streamlit" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "AXIA Streamlit UI Service"
```

#### 2-4. MT5自動起動（30分）

```xml
名前: AXIA_MT5
説明: MetaTrader 5起動
トリガー: システム起動時
アクション:
  プログラム: C:\Program Files\MetaTrader 5\terminal64.exe
  引数: (なし)
設定:
  ✅ 最高の特権で実行
  ✅ ユーザーがログオンしているかどうかにかかわらず実行
```

**PowerShellコマンド:**
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Program Files\MetaTrader 5\terminal64.exe"

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$principal = New-ScheduledTaskPrincipal -UserId "Administrator" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName "AXIA_MT5" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "AXIA MetaTrader 5"
```

---

### Step 3: 統合テスト（1.5時間）

#### 3-1. 4プロセス同時起動テスト（30分）

**手順:**
1. タスクスケジューラで4タスクを手動実行
2. タスクマネージャーでプロセス確認:
   - `python.exe` (order_manager)
   - `python.exe` (streamlit)
   - `terminal64.exe` (MT5)
3. 各プロセスのログ確認

**確認項目:**
```
✅ order_manager起動成功
✅ Streamlit起動成功（ポート8501）
✅ MT5起動成功
✅ Redis接続成功（全プロセス）
✅ AWS接続成功（IAM Role）
```

#### 3-2. メモリ使用量測定（30分）

**PowerShellスクリプト:**
```powershell
# memory_monitor.ps1
Write-Host "=== AXIA TSS Memory Monitor ===" -ForegroundColor Cyan

# システム全体
$os = Get-WmiObject Win32_OperatingSystem
$totalRAM = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$freeRAM = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$usedRAM = [math]::Round($totalRAM - $freeRAM, 2)
$usagePercent = [math]::Round(($usedRAM / $totalRAM) * 100, 2)

Write-Host "System: $usedRAM GB / $totalRAM GB ($usagePercent%)"

# 各プロセス
$processes = @("python", "terminal64")
foreach ($proc in $processes) {
    $running = Get-Process -Name $proc -ErrorAction SilentlyContinue
    if ($running) {
        $memMB = [math]::Round(($running | Measure-Object WorkingSet -Sum).Sum / 1MB, 2)
        Write-Host "$proc : $memMB MB" -ForegroundColor Green
    }
}
```

**判定基準:**
- ✅ メモリ使用率 < 80%: 正常
- ⚠️ メモリ使用率 80-90%: 注意（ピーク時監視）
- ❌ メモリ使用率 > 90%: t3.mediumへのアップグレード検討

#### 3-3. 注文機能統合テスト（30分）

**テストケース:**

1. **BUY注文テスト**
```
手順:
1. Streamlitで注文パネル開く
2. USDJPY, 0.1 lot, TP=50pips, SL=25pips 入力
3. BUYボタンクリック

期待結果:
✅ Streamlit: 成功メッセージ表示
✅ SQS: メッセージ送信成功
✅ order_manager: ログに受信確認
✅ MT5: 注文実行（MOCKモードの場合はログのみ）
```

2. **SELL注文テスト**
```
手順:
1. USDJPY, 0.1 lot, TP=50pips, SL=25pips 入力
2. SELLボタンクリック

期待結果: 同上
```

3. **エラーハンドリングテスト**
```
手順:
1. 不正なロット数入力（0.001など）
2. 注文実行

期待結果:
✅ バリデーションエラー表示
❌ SQSには送信されない
```

---

## ✅ Week 3完了条件

### 必須機能

```
✅ 注文機能完全実装
  ✅ SQS order_publisher動作
  ✅ Streamlit → SQS → order_manager → MT5連携
  ✅ 注文結果表示

✅ リアルタイムデータ対応
  ✅ OhlcvDataProvider統合
  ✅ Redis鮮度メタデータ
  ✅ データ鮮度可視化（✅/ℹ️/⚠️）
  ⏳ 🔄最新ボタン動作（実装済み・未テスト）

⏳ Windows EC2デプロイ
  ✅ EC2スケールアップ（t3.small）
  ✅ セキュリティグループ設定
  ✅ Streamlit起動確認
  ⏳ タスクスケジューラ4プロセス
  ⏳ 自動起動確認
  ⏳ 統合テスト完了
```

### パフォーマンス指標

| 項目 | 目標 | 実績 | 判定 |
|------|------|------|------|
| **注文送信** | 1秒以内 | 未測定 | ⏳ |
| **チャート表示** | 1秒以内 | 0.094s | ✅ |
| **Redisキャッシュ** | 100ms以内 | 0.015s〜0.094s | ✅ |
| **🔄最新更新** | 2秒以内 | 未測定 | ⏳ |
| **メモリ使用量** | < 80% | 未測定 | ⏳ |

---

## 📊 実装統計

### 新規・更新ファイル（Week 3全体）

| ファイル | 状態 | 行数 | Day |
|---------|------|------|-----|
| `order_publisher.py` | 🆕新規 | 120行 | Day 1 |
| `container.py` | 🔄更新 | +15行 | Day 1 |
| `redis_ohlcv_data_repository.py` | 🔄更新 | +150行 | Day 2 |
| `ohlcv_data_provider.py` | 🔄更新 | +180行 | Day 2 |
| `chart_data_source.py` | 🔄書換 | 200行 | Day 2 |
| `trading_page.py` | 🔄更新 | +150行 | Day 1+2 |
| `price_chart.py` | 🔄更新 | +50行 | Day 2 |
| `chart_renderer.py` | 🔄更新 | +30行 | Day 2 |

**合計**: 約895行

---

## 💾 コミット履歴

### Day 1コミット ✅

```bash
git add .
git commit -m "feat(week3): Day 1 - Order function implementation complete

- Add SQSOrderPublisher with MOCK mode support
- Update DIContainer to inject order publisher
- Implement complete order panel in trading_page
- Add order validation and execution flow
- Support BUY/SELL order submission

Tested: Order submission working in MOCK mode
"
```

### Day 2コミット ✅

```bash
git add .
git commit -m "feat(week3): Day 2 - Real-time data freshness complete

- Add Redis metadata functions (save/load with metadata)
- Implement data freshness check in OhlcvDataProvider
- Fix price_chart.py to use get_chart_data_source()
- Fix yfinance integration in OhlcvDataProvider
- Add time index conversion for chart rendering
- Update chart_renderer data source display

Tested: 
- ✅ Chart display with USDJPY H1 (240 rows from Redis)
- ✅ Redis cache hit (0.015s〜0.094s)
- ✅ Multiple timeframes working (M1, M5, H1)
- ✅ EC2 deployment with t3.small
- ✅ ElastiCache Redis connection successful
"
```

### Day 3コミット予定 ⏳

```bash
git add .
git commit -m "feat(week3): Day 3 - EC2 deployment and task scheduler complete

- EC2 instance upgraded to t3.small (2GB RAM)
- Security group configured for Streamlit (port 8501)
- Windows Firewall configured
- Task Scheduler setup for 4 processes:
  - order_manager (startup)
  - data_collector (daily 07:00)
  - Streamlit (startup, 5min delay)
  - MT5 (startup)
- Integration tests completed

Tested:
- ✅ Browser access to Streamlit UI
- ✅ 4 processes auto-start working
- ✅ Memory usage < 80%
- ✅ BUY/SELL order submission
- ✅ Redis cache performance
"
```

---

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

---

## 📝 Day 3 午後 実行チェックリスト

### ✅ 完了項目
- [x] EC2スケールアップ（t3.small）
- [x] セキュリティグループ設定
- [x] Windowsファイアウォール設定
- [x] Git Pull実行
- [x] Streamlit起動確認
- [x] Redis接続確認
- [x] MT5認証確認
- [x] チャート描画確認
- [x] ブラウザアクセス確認
- [x] パブリックIP確認

### ⏳ 残り作業
- [ ] スクリーンショット取得
- [ ] タスクスケジューラ設定（4タスク）
- [ ] 4プロセス同時起動テスト
- [ ] メモリ使用量測定
- [ ] BUY注文テスト
- [ ] SELL注文テスト
- [ ] 最終コミット

---

## 🎯 Day 3 完了判定

以下の全項目が完了でDay 3完了：

1. ✅ ブラウザからStreamlit UIアクセス成功
2. ✅ タスクスケジューラ4タスク設定完了
3. ✅ EC2再起動後の自動起動確認
4. ✅ メモリ使用量 < 80%
5. ✅ 注文機能動作確認（BUY/SELL）
6. ✅ 統合テスト全項目パス

---

