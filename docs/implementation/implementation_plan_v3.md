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

# 📋 Day 3午後 実装計画（Provider命名版 + ドキュメント更新タスク追加）

## 🎯 更新された実装目標

```
✅ 命名規則確定: Provider suffix採用

実装タスク:
1. MT5PriceProvider実装（1時間）
2. MT5AccountProvider実装（1.5時間）
3. DIContainer更新（30分）
4. Streamlit UI統合（1.5時間）
5. 📝 ドキュメント更新（30分）★追加★
```

---

## 📅 Day 3午後スケジュール（13:00-17:30）

### **13:00-14:00（1時間）: MT5PriceProvider実装**

#### **ファイル作成**
```
src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py
```

#### **実装内容**
```python
# src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py
"""MT5価格情報プロバイダー

このモジュールは、MetaTrader 5プラットフォームからリアルタイム価格情報を
取得・提供するプロバイダーです。

命名規則:
    - Suffix: Provider
    - 理由: リアルタイムデータ提供の責務を持つ
    - パターン: OhlcvDataProviderと一貫性

特徴:
    - リアルタイム価格取得（Bid/Ask）
    - シンボル情報取得
    - スプレッド計算（pips）
    - MT5接続状態の自動確認

依存関係:
    - MetaTrader5: MT5 Pythonライブラリ
    - MT5Connection: MT5接続管理クラス

使用例:
    >>> from src.infrastructure.di.container import container
    >>> 
    >>> price_provider = container.get_mt5_price_provider()
    >>> 
    >>> # 現在価格取得
    >>> price_info = price_provider.get_current_price('USDJPY')
    >>> print(f"Ask: {price_info['ask']}, Spread: {price_info['spread']} pips")
"""

import logging
from typing import Dict, Optional, Tuple
import MetaTrader5 as mt5
from datetime import datetime

logger = logging.getLogger(__name__)


class MT5PriceProvider:
    """
    MT5価格情報プロバイダー
    
    MetaTrader 5プラットフォームからリアルタイム価格情報を提供します。
    
    命名規則:
        - クラス名: MT5PriceProvider
        - Suffix: Provider（データ提供の責務）
        - 既存パターン: OhlcvDataProviderと同じ
    
    Attributes:
        connection (MT5Connection): MT5接続管理インスタンス
    
    Note:
        - Infrastructure層のプロバイダーパターン
        - Application層から依存性注入で利用
        - エラー時はNoneを返却（上位層で判断）
    """
    
    def __init__(self, connection: 'MT5Connection'):
        """
        初期化
        
        Args:
            connection: MT5接続管理インスタンス
        """
        self.connection = connection
        logger.info("MT5PriceProvider initialized")
    
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """
        現在価格を取得
        
        Args:
            symbol: 通貨ペア（例: "USDJPY"）
        
        Returns:
            dict: {
                'symbol': str,
                'bid': float,
                'ask': float,
                'spread': float,  # pips
                'time': datetime
            }
            None: 取得失敗時
        """
        try:
            if not self.connection.ensure_connected():
                logger.error("MT5 not connected")
                return None
            
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning(f"Failed to get tick for {symbol}")
                return None
            
            # スプレッド計算（pips）
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                point = symbol_info.point
                spread_pips = (tick.ask - tick.bid) / point
            else:
                spread_pips = 0.0
            
            return {
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': spread_pips,
                'time': datetime.fromtimestamp(tick.time)
            }
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}", exc_info=True)
            return None
    
    def get_bid_ask(self, symbol: str) -> Optional[Tuple[float, float]]:
        """
        Bid/Ask価格を取得
        
        Args:
            symbol: 通貨ペア
        
        Returns:
            tuple: (bid, ask)
            None: 取得失敗時
        """
        price_info = self.get_current_price(symbol)
        if price_info:
            return (price_info['bid'], price_info['ask'])
        return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        シンボル情報を取得
        
        Args:
            symbol: 通貨ペア
        
        Returns:
            dict: {
                'symbol': str,
                'digits': int,
                'point': float,
                'trade_contract_size': float,
                'volume_min': float,
                'volume_max': float,
                'volume_step': float
            }
            None: 取得失敗時
        """
        try:
            if not self.connection.ensure_connected():
                return None
            
            info = mt5.symbol_info(symbol)
            if info is None:
                logger.warning(f"Symbol info not found: {symbol}")
                return None
            
            return {
                'symbol': symbol,
                'digits': info.digits,
                'point': info.point,
                'trade_contract_size': info.trade_contract_size,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step
            }
            
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}", exc_info=True)
            return None
```

---

### **14:00-15:30（1.5時間）: MT5AccountProvider実装**

#### **ファイル作成**
```
src/infrastructure/gateways/brokers/mt5/mt5_account_provider.py
```

#### **実装内容（NYクローズ基準対応版）**
```python
# src/infrastructure/gateways/brokers/mt5/mt5_account_provider.py
"""MT5口座情報プロバイダー

このモジュールは、MetaTrader 5プラットフォームから口座情報を
取得・提供するプロバイダーです。

命名規則:
    - Suffix: Provider
    - 理由: 口座情報提供の責務を持つ
    - パターン: MT5PriceProviderと一貫性

特徴:
    - 口座残高・証拠金情報取得
    - 本日損益計算（NYクローズ基準）
    - 証拠金率計算

依存関係:
    - MetaTrader5: MT5 Pythonライブラリ
    - MT5Connection: MT5接続管理クラス
    - Settings: NYクローズ時刻設定

使用例:
    >>> from src.infrastructure.di.container import container
    >>> 
    >>> account_provider = container.get_mt5_account_provider()
    >>> 
    >>> # 口座情報取得
    >>> account_info = account_provider.get_account_info()
    >>> print(f"Balance: {account_info['balance']}")
    >>> 
    >>> # 本日損益取得
    >>> today_pl = account_provider.calculate_today_pl()
    >>> print(f"Today P/L: {today_pl['amount']}")
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pytz

logger = logging.getLogger(__name__)


class MT5AccountProvider:
    """
    MT5口座情報プロバイダー
    
    MetaTrader 5プラットフォームから口座情報を提供します。
    
    命名規則:
        - クラス名: MT5AccountProvider
        - Suffix: Provider（データ提供の責務）
        - 既存パターン: MT5PriceProviderと同じ
    
    Attributes:
        connection (MT5Connection): MT5接続管理インスタンス
    
    Note:
        - Infrastructure層のプロバイダーパターン
        - NYクローズ基準で"本日"を判定
        - エラー時はNoneを返却
    """
    
    def __init__(self, connection: 'MT5Connection'):
        """
        初期化
        
        Args:
            connection: MT5接続管理インスタンス
        """
        self.connection = connection
        logger.info("MT5AccountProvider initialized")
    
    def get_account_info(self) -> Optional[Dict]:
        """
        口座情報を取得
        
        Returns:
            dict: {
                'balance': float,          # 残高
                'equity': float,           # 有効証拠金
                'margin': float,           # 使用証拠金
                'free_margin': float,      # 余剰証拠金
                'margin_level': float,     # 証拠金率（%）
                'profit': float,           # 含み損益
                'currency': str,           # 通貨
                'leverage': int            # レバレッジ
            }
            None: 取得失敗時
        """
        try:
            if not self.connection.ensure_connected():
                logger.error("MT5 not connected")
                return None
            
            account = mt5.account_info()
            if account is None:
                logger.error("Failed to get account info")
                return None
            
            # 証拠金率計算（%）
            if account.margin > 0:
                margin_level = (account.equity / account.margin) * 100
            else:
                margin_level = 0.0 if account.equity == 0 else float('inf')
            
            return {
                'balance': account.balance,
                'equity': account.equity,
                'margin': account.margin,
                'free_margin': account.margin_free,
                'margin_level': margin_level,
                'profit': account.profit,
                'currency': account.currency,
                'leverage': account.leverage
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}", exc_info=True)
            return None
    
    def get_balance(self) -> Optional[float]:
        """残高を取得"""
        account = self.get_account_info()
        return account['balance'] if account else None
    
    def get_margin_info(self) -> Optional[Dict]:
        """
        証拠金情報を取得
        
        Returns:
            dict: {
                'margin': float,
                'free_margin': float,
                'margin_level': float
            }
        """
        account = self.get_account_info()
        if account:
            return {
                'margin': account['margin'],
                'free_margin': account['free_margin'],
                'margin_level': account['margin_level']
            }
        return None
    
    def calculate_today_pl(self) -> Optional[Dict]:
        """
        本日の損益を計算（NYクローズ基準）
        
        NYクローズ（UTC 21:00夏時間 / 22:00冬時間）を"本日"の開始とします。
        
        Returns:
            dict: {
                'amount': float,      # 金額
                'percentage': float   # %
            }
            None: 取得失敗時
        """
        try:
            if not self.connection.ensure_connected():
                return None
            
            # 現在時刻（UTC）
            now = datetime.now(pytz.UTC)
            
            # NYクローズ基準の"今日"の開始時刻を計算
            # 夏時間（3月第2日曜～11月第1日曜）: UTC 21:00
            # 冬時間: UTC 22:00
            # 簡易判定: 3-10月は夏時間、11-2月は冬時間
            if 3 <= now.month <= 10:
                ny_close_hour = 21  # 夏時間
            else:
                ny_close_hour = 22  # 冬時間
            
            # 今日のNYクローズ時刻
            today_ny_close = now.replace(hour=ny_close_hour, minute=0, second=0, microsecond=0)
            
            # もし現在時刻が今日のNYクローズ前なら、昨日のNYクローズが基準
            if now < today_ny_close:
                today_start = today_ny_close - timedelta(days=1)
            else:
                today_start = today_ny_close
            
            logger.info(f"Calculating today's P/L from NY Close: {today_start}")
            
            # 本日の取引履歴を取得
            history = mt5.history_deals_get(today_start, now)
            
            if history is None:
                logger.warning("Failed to get today's history")
                return {'amount': 0.0, 'percentage': 0.0}
            
            # 決済済み損益の合計
            realized_pl = sum(deal.profit for deal in history if deal.entry == 1)  # entry=1は決済
            
            # 現在の含み損益
            account = self.get_account_info()
            if account:
                unrealized_pl = account['profit']
                total_pl = realized_pl + unrealized_pl
                
                # %計算
                if account['balance'] > 0:
                    pl_percentage = (total_pl / account['balance']) * 100
                else:
                    pl_percentage = 0.0
                
                logger.info(
                    f"Today's P/L: Realized={realized_pl:.2f}, "
                    f"Unrealized={unrealized_pl:.2f}, "
                    f"Total={total_pl:.2f} ({pl_percentage:.2f}%)"
                )
                
                return {
                    'amount': total_pl,
                    'percentage': pl_percentage
                }
            
            return {'amount': realized_pl, 'percentage': 0.0}
            
        except Exception as e:
            logger.error(f"Error calculating today's P/L: {e}", exc_info=True)
            return None
```

---

### **15:30-16:00（30分）: DIContainer更新**

#### **ファイル更新**
```
src/infrastructure/di/container.py
```

#### **追加内容**
```python
# src/infrastructure/di/container.py

# インポート追加
from src.infrastructure.gateways.brokers.mt5.mt5_price_provider import MT5PriceProvider
from src.infrastructure.gateways.brokers.mt5.mt5_account_provider import MT5AccountProvider

class DIContainer:
    """依存性注入コンテナ"""
    
    def __init__(self):
        # 既存...
        self._mt5_price_provider: Optional[MT5PriceProvider] = None
        self._mt5_account_provider: Optional[MT5AccountProvider] = None
    
    def get_mt5_price_provider(self) -> MT5PriceProvider:
        """
        MT5価格プロバイダーを取得（シングルトン）
        
        Returns:
            MT5PriceProvider: リアルタイム価格情報プロバイダー
        
        Note:
            - 命名規則: Provider suffix（データ提供の責務）
            - パターン: OhlcvDataProviderと一貫性
        """
        if not self._mt5_price_provider:
            self._mt5_price_provider = MT5PriceProvider(
                connection=self.get_mt5_connection()
            )
            logger.info("MT5PriceProvider initialized")
        return self._mt5_price_provider
    
    def get_mt5_account_provider(self) -> MT5AccountProvider:
        """
        MT5口座情報プロバイダーを取得（シングルトン）
        
        Returns:
            MT5AccountProvider: 口座情報プロバイダー
        
        Note:
            - 命名規則: Provider suffix（データ提供の責務）
            - NYクローズ基準の損益計算を提供
        """
        if not self._mt5_account_provider:
            self._mt5_account_provider = MT5AccountProvider(
                connection=self.get_mt5_connection()
            )
            logger.info("MT5AccountProvider initialized")
        return self._mt5_account_provider
```

---

### **16:00-17:00（1時間）: Streamlit UI統合**

#### **header.py更新**
```python
# src/presentation/ui/streamlit/layouts/header.py

import streamlit as st
import logging
from src.infrastructure.di.container import DIContainer

logger = logging.getLogger(__name__)
container = DIContainer()


def render_header_metrics():
    """ヘッダーメトリクスの表示（リアルタイムMT5データ）"""
    st.markdown("## AXIA - Trading Strategy System -")
    
    # MT5プロバイダー取得
    try:
        account_provider = container.get_mt5_account_provider()
        price_provider = container.get_mt5_price_provider()
    except Exception as e:
        logger.error(f"Failed to initialize MT5 providers: {e}")
        st.error("⚠️ MT5プロバイダーの初期化に失敗しました")
        return
    
    # データ取得
    account_info = account_provider.get_account_info()
    today_pl = account_provider.calculate_today_pl()
    
    # デフォルト通貨ペアの価格取得
    default_symbol = "USDJPY"
    price_info = price_provider.get_current_price(default_symbol)
    
    # システムステータス
    status_cols = st.columns(4)
    
    # 現在価格
    with status_cols[0]:
        if price_info:
            st.metric(
                f"{price_info['symbol']} 価格",
                f"{price_info['ask']:.3f}",
                f"{price_info['spread']:.1f} pips"
            )
        else:
            st.metric("現在価格", "取得中...", None)
    
    # 本日損益（NYクローズ基準）
    with status_cols[1]:
        if today_pl:
            amount = today_pl['amount']
            percentage = today_pl['percentage']
            
            delta_color = "normal" if amount >= 0 else "inverse"
            
            st.metric(
                "本日損益",
                f"{percentage:+.2f}%",
                f"¥{amount:+,.0f}",
                delta_color=delta_color
            )
        else:
            st.metric("本日損益", "取得中...", None)
    
    # ポジション数（後で実装）
    with status_cols[2]:
        st.metric("ポジション", "0/3", None)
    
    # 証拠金率
    with status_cols[3]:
        if account_info:
            margin_level = account_info['margin_level']
            
            if margin_level >= 300:
                status = "安全"
                status_color = "normal"
            elif margin_level >= 200:
                status = "注意"
                status_color = "normal"
            elif margin_level >= 100:
                status = "警告"
                status_color = "inverse"
            else:
                status = "危険"
                status_color = "inverse"
            
            st.metric(
                "証拠金率",
                f"{margin_level:.0f}%",
                status,
                delta_color=status_color
            )
        else:
            st.metric("証拠金率", "取得中...", None)
```

#### **trading_page.py更新（_execute_order関数）**
```python
# src/presentation/ui/streamlit/pages/trading_page.py

def _execute_order(
    symbol: str,
    action: str,
    lot_size: float,
    tp_pips: int,
    sl_pips: int,
    order_publisher
):
    """注文実行（SQS送信）- 現在価格ベース"""
    try:
        # MT5価格プロバイダー取得
        price_provider = container.get_mt5_price_provider()
        
        # 現在価格取得
        price_info = price_provider.get_current_price(symbol)
        
        if price_info is None:
            st.error(f"❌ {symbol}の現在価格を取得できませんでした")
            logger.error(f"Failed to get price for {symbol}")
            return
        
        # BUY=ask, SELL=bid
        current_price = price_info['ask'] if action == "BUY" else price_info['bid']
        
        logger.info(
            f"Current price for {symbol} {action}: {current_price} "
            f"(spread={price_info['spread']:.1f} pips)"
        )
        
        # pip値取得
        symbol_info = price_provider.get_symbol_info(symbol)
        if symbol_info:
            pip_value = symbol_info['point'] * 10
        else:
            pip_value = 0.01 if 'JPY' in symbol else 0.0001
        
        # TP/SL価格計算
        if action == "BUY":
            tp_price = current_price + (tp_pips * pip_value)
            sl_price = current_price - (sl_pips * pip_value)
        else:
            tp_price = current_price - (tp_pips * pip_value)
            sl_price = current_price + (sl_pips * pip_value)
        
        # 注文データ作成
        order_data = {
            'symbol': symbol,
            'order_action': action,
            'order_type': 'MARKET',
            'lot_size': lot_size,
            'tp_price': round(tp_price, 5),
            'sl_price': round(sl_price, 5),
            'comment': 'Streamlit_Manual_Order'
        }
        
        logger.info(f"Executing order: {order_data}")
        
        # SQS送信
        with st.spinner('注文送信中...'):
            success, message = order_publisher.send_order(order_data)
        
        if success:
            rr = tp_pips / sl_pips if sl_pips > 0 else 0
            risk_amount = lot_size * sl_pips * 100
            profit_amount = lot_size * tp_pips * 100
            
            is_mock = message.startswith('mock-')
            mode_label = "🧪 **MOCK MODE**" if is_mock else "✅"
            
            st.success(f"""
            {mode_label} **{action}注文を送信しました**
            
            **注文内容**:
            - 通貨ペア: `{symbol}`
            - ロット: `{lot_size}`
            - エントリー: `{current_price:.5f}` (現在価格)
            - スプレッド: `{price_info['spread']:.1f} pips`
            - TP: `{tp_price:.5f}` ({tp_pips} pips)
            - SL: `{sl_price:.5f}` ({sl_pips} pips)
            - R/R比: `{rr:.2f}`
            
            **リスク・リターン**:
            - 想定損失: ¥{risk_amount:,.0f}
            - 想定利益: ¥{profit_amount:,.0f}
            
            **処理状況**:
            - MessageID: `{message[:30]}...`
            {('- ⚠️ AWS未接続のため実際の注文は実行されません' if is_mock else '- order_managerで処理中...')}
            """)
            
            logger.info(f"Order sent: {symbol} {action} @ {current_price}, MessageID={message}")
            
        else:
            st.error(f"❌ **注文送信に失敗しました**\n\n**エラー**: {message}")
            logger.error(f"Order send failed: {message}")
            
    except Exception as e:
        st.error(f"❌ **注文処理エラー**\n\n{str(e)}")
        logger.error(f"Order execution error: {e}", exc_info=True)
```

---

### **17:00-17:30（30分）: 📝 ドキュメント更新タスク ★新規追加★**

#### **タスク1: architecture_patterns.md更新**

**ファイル**: `docs/logical_design/architecture_patterns.md`

**追加セクション**: 「9. 命名規則」（新規セクション）

```markdown
## 9. 命名規則（Naming Conventions）

### 9.1 Infrastructure層のSuffix規則

AXIAでは、Infrastructure層のクラス命名に以下のSuffixルールを適用します。

| Suffix | 責務 | 使用例 | 該当ファイル |
|--------|------|--------|-------------|
| **Repository** | データ永続化 | `DynamoDBKillSwitchRepository` | `src/infrastructure/persistence/dynamodb/` |
| **Provider** | データ提供 | `OhlcvDataProvider`<br/>`MT5PriceProvider`<br/>`MT5AccountProvider` | `src/infrastructure/gateways/market_data/`<br/>`src/infrastructure/gateways/brokers/mt5/` |
| **Gateway** | 外部API統合 | `YFinanceGateway` | `src/infrastructure/gateways/market_data/` |
| **Client** | 接続管理 | `RedisClient` | `src/infrastructure/persistence/redis/` |
| **Connection** | 接続管理（専用） | `MT5Connection` | `src/infrastructure/gateways/brokers/mt5/` |
| **Executor** | 実行処理 | `MT5OrderExecutor` | `src/infrastructure/gateways/brokers/mt5/` |
| **Collector** | データ収集 | `MT5DataCollector` | `src/infrastructure/gateways/brokers/mt5/` |
| **Publisher** | メッセージ送信 | `SQSOrderPublisher` | `src/infrastructure/gateways/messaging/sqs/` |
| **Listener** | メッセージ受信 | `SQSQueueListener` | `src/infrastructure/gateways/messaging/sqs/` |

### 9.2 Domain層のSuffix規則

| Suffix | 責務 | 使用例 | 該当ファイル |
|--------|------|--------|-------------|
| **Service** | ドメインロジック | `OrderValidationService` | `src/domain/services/` |
| **Entity** | エンティティ | `Order` | `src/domain/entities/` |

### 9.3 Provider vs Gateway vs Service

#### Provider（推奨: データ提供）
```python
# データを継続的に提供する責務
class OhlcvDataProvider:
    """複数ソースからOHLCVデータを提供"""
    pass

class MT5PriceProvider:
    """MT5からリアルタイム価格を提供"""
    pass
```

#### Gateway（推奨: 外部API統合）
```python
# 外部APIとのI/F役割
class YFinanceGateway:
    """Yahoo Finance APIとの統合"""
    pass
```

#### Service（Domain層専用）
```python
# ドメインロジック
class OrderValidationService:
    """注文検証のドメインサービス"""
    pass
```

**注意**: Infrastructure層では`Service`は使用せず、`Provider`または`Gateway`を使用します。

### 9.4 命名基準の適用例

#### ✅ 正しい命名
```python
# Infrastructure層
src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py
class MT5PriceProvider:  # データ提供 → Provider

src/infrastructure/gateways/market_data/yfinance_gateway.py
class YFinanceGateway:  # 外部API → Gateway

# Domain層
src/domain/services/order_validation.py
class OrderValidationService:  # ドメインロジック → Service
```

#### ❌ 誤った命名
```python
# Infrastructure層でServiceを使用（混同リスク）
class MT5PriceService:  # ❌ Domain層のServiceと混同

# Domain層でProviderを使用（責務不明確）
class OrderValidationProvider:  # ❌ Providerは技術層用
```

### 9.5 実装ガイドライン

1. **新規クラス作成時**
   - 責務を明確化する
   - レイヤーに応じたSuffixを選択
   - 既存パターンとの一貫性を確認

2. **命名の判断基準**
   ```
   Q: データを提供する？
   → Yes: Provider
   
   Q: 外部APIと統合する？
   → Yes: Gateway
   
   Q: ドメインロジックを実装？
   → Yes: Service（Domain層のみ）
   
   Q: データを永続化する？
   → Yes: Repository
   ```

3. **レビュー時の確認事項**
   - [ ] Suffixがレイヤーに適切か
   - [ ] 既存パターンと一貫性があるか
   - [ ] クラス名から責務が明確か

---

**Version**: 1.1  
**Updated**: 2025-10-19  
**Change**: 命名規則セクション追加（MT5Provider実装に伴う標準化）
```

---

#### **タスク2: basic_design.md更新**

**ファイル**: `docs/basic_design.md`

**更新箇所**: セクション3.2「src/ディレクトリ詳細」のMT5関連部分

```markdown
### 3.2 src/ディレクトリ詳細

```
src/
└── infrastructure/
    └── gateways/
        └── brokers/
            └── mt5/
                ├── mt5_connection.py           # ✅ MT5接続管理
                ├── mt5_order_executor.py       # ✅ 注文実行
                ├── mt5_data_collector.py       # ✅ OHLCVデータ収集
                ├── mt5_price_provider.py       # 🆕 Week 3: 価格情報提供
                ├── mt5_account_provider.py     # 🆕 Week 3: 口座情報提供
                └── mt5_position_provider.py    # ⏳ Week 4: ポジション情報提供
```

**命名規則**: 
- `*_provider.py`: データ提供の責務（Provider suffix）
- `*_executor.py`: 実行処理の責務（Executor suffix）
- `*_collector.py`: データ収集の責務（Collector suffix）
- `*_connection.py`: 接続管理の責務（Connection suffix）

詳細は [architecture_patterns.md](logical_design/architecture_patterns.md#9-命名規則) を参照。
```

---

#### **タスク3: implementation_plan_v3.md更新**

**ファイル**: `docs/implementation/implementation_plan_v3.md`

**更新箇所**: Day 3午後のファイル名を修正

```markdown
### **Day 3（月）: EC2デプロイ + 現在価格実装**

#### **午後（4時間）: 現在価格 + 口座情報実装**

```
13:00-14:00（1時間）: MT5価格取得プロバイダー実装
  ├─ MT5PriceProvider作成（30分）  ★修正★
  │  ├─ get_current_price(symbol) → dict
  │  ├─ get_bid_ask(symbol) → tuple
  │  └─ get_symbol_info(symbol) → dict
  └─ DIContainer統合（30分）

14:00-15:30（1.5時間）: MT5口座情報プロバイダー実装
  ├─ MT5AccountProvider作成（1時間）  ★修正★
  │  ├─ get_account_info() → dict
  │  ├─ get_balance() → float
  │  ├─ get_margin_info() → dict
  │  └─ calculate_today_pl() → float（NYクローズ基準）
  └─ DIContainer統合（30分）

15:30-17:00（1.5時間）: ヘッダーメトリクス実装
  ├─ header.py更新（1時間）
  │  ├─ MT5AccountProvider呼び出し
  │  ├─ リアルタイム表示
  │  └─ エラーハンドリング
  └─ trading_page.py現在価格更新（30分）
     ├─ MT5PriceProvider呼び出し
     └─ _execute_order()修正

17:00-17:30（30分）: ドキュメント更新  ★追加★
  ├─ architecture_patterns.md更新
  ├─ basic_design.md更新
  └─ implementation_plan_v3.md更新
```

**実装ファイル**:
- ✅ `src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py`（新規）
- ✅ `src/infrastructure/gateways/brokers/mt5/mt5_account_provider.py`（新規）
- 🔄 `src/infrastructure/di/container.py`（更新）
- 🔄 `src/presentation/ui/streamlit/layouts/header.py`（更新）
- 🔄 `src/presentation/ui/streamlit/pages/trading_page.py`（更新）

**ドキュメント更新**:
- 📝 `docs/logical_design/architecture_patterns.md`（命名規則追加）
- 📝 `docs/basic_design.md`（ディレクトリ構造更新）
- 📝 `docs/implementation/implementation_plan_v3.md`（本ファイル）
```

---

#### **タスク4: current_status.md更新**

**ファイル**: `docs/implementation/current_status.md`

**更新箇所**: セクション4.2「部分実装ファイル」

```markdown
### 4.2 完全実装済みファイル（✅ 100%）

| ファイル | 行数 | 実装日 | 主要機能 | テスト状況 |
|---------|------|-------|---------|-----------|
| **mt5_price_provider.py** | 150行 | 10/19 | リアルタイム価格取得 | 🔄 テスト予定 |
| **mt5_account_provider.py** | 180行 | 10/19 | 口座情報・本日損益（NYクローズ） | 🔄 テスト予定 |
| （既存ファイル省略） |
```

---

## 📊 Day 3午後 完了チェックリスト

### **実装タスク**
- [ ] MT5PriceProvider実装（150行、1時間）
- [ ] MT5AccountProvider実装（180行、1.5時間）
- [ ] DIContainer更新（30分）
- [ ] header.py更新（1時間）
- [ ] trading_page.py更新（30分）

### **ドキュメント更新タスク ★追加★**
- [ ] `architecture_patterns.md`に命名規則セクション追加
- [ ] `basic_design.md`のディレクトリ構造更新
- [ ] `implementation_plan_v3.md`のファイル名修正
- [ ] `current_status.md`に新規ファイル追加

### **動作確認**
- [ ] Streamlitヘッダーに本日損益表示
- [ ] Streamlitヘッダーに現在価格表示
- [ ] trading_page現在価格ベース注文動作
- [ ] NYクローズ基準の損益計算確認

---

## 🎯 次のステップ

Day 3午後完了後、以下を確認：

1. **Provider実装の動作確認**
   - ヘッダーメトリクスが正常に表示されるか
   - 現在価格ベースの注文が動作するか

2. **ドキュメント整合性確認**
   - 命名規則が各ドキュメントで統一されているか
   - ファイル一覧が最新状態か

3. **Day 4準備**
   - MT5PositionProvider設計レビュー
   - position_page.py書き換え準備

---

**準備完了です！実装を開始しますか？** 🚀