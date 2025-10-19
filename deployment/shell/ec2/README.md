## EC2での実行手順

### Phase 1: ファイル配置（5分）

1. **start_streamlit.ps1** - Streamlit UI起動
2. **start_order_manager.ps1** - Order Manager起動
3. **start_mt5_connector.ps1** - MT5接続管理
4. **run_data_collector.ps1** - 日次データ収集
5. **register_scheduled_tasks.ps1** - タスク一括登録

### Phase 2: タスク登録（3分）

```powershell
# 管理者権限のPowerShellで実行
cd C:\Users\Administrator\Projects\axia-tss\deployment\shell\ec2

# タスク一括登録実行
.\register_scheduled_tasks.ps1

# 実行結果確認
# ✓ AXIA_Streamlit [Ready]
# ✓ AXIA_Order_Manager [Ready]
# ✓ AXIA_MT5 [Ready]
# ✓ AXIA_Data_Collector [Ready]
```

### Phase 3: 動作確認（10分）

```powershell
# 1. タスクスケジューラを開く
taskschd.msc

# 2. 各タスクを手動実行してテスト
#    AXIA_Streamlit を右クリック → 実行

# 3. ログ確認
Get-Content C:\Users\Administrator\axia-logs\streamlit.log -Tail 20

# 4. プロセス確認
Get-Process | Where-Object { $_.ProcessName -like "*streamlit*" -or $_.ProcessName -like "*python*" }

# 5. Streamlitアクセス確認
# ブラウザで http://localhost:8501 を開く
```

### Phase 4: EC2再起動テスト（5分）

```powershell
# 1. 現在のプロセスを全て停止
Stop-Process -Name "streamlit", "python", "terminal64" -Force -ErrorAction SilentlyContinue

# 2. EC2再起動
Restart-Computer

# 3. 再起動後、RDP再接続（2-3分待機）

# 4. プロセス自動起動確認
Get-Process | Where-Object { $_.ProcessName -like "*streamlit*" -or $_.ProcessName -like "*python*" -or $_.ProcessName -like "*terminal64*" }

# 5. ログ確認
Get-Content C:\Users\Administrator\axia-logs\*.log -Tail 10
```

---

## 🔍 トラブルシューティング

### よくある問題と解決策

| 問題 | 原因 | 解決策 |
|------|------|--------|
| タスクが実行されない | ExecutionPolicy制限 | `Set-ExecutionPolicy RemoteSigned -Force` |
| Conda環境が見つからない | パス設定ミス | スクリプト内の `$CONDA_ENV` を確認 |
| MT5が起動しない | パス間違い | スクリプト内の `$MT5_TERMINAL_PATH` を確認 |
| ログが作成されない | 権限不足 | `C:\Users\Administrator\axia-logs` の権限確認 |

---
