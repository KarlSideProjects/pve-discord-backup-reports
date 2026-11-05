# AI agent：安裝與維護

[返回圖解首頁](../README.md)

管理 PVE 主機的備份結果報告程式與部署方式。程式讀取 systemd 本次備份的 journal，整理成 Discord 表格，再經由 PVE Notifications 既有 Webhook 發送。PBS 儲存備份資料，本倉庫不在 PBS 上執行。

## 目前架構

`systemd timer → 備份 service → pbs-report → PVE Notifications → Discord`

- `pbs-guarded-backup.service` 執行 VM／CT 備份；`pve-host-config-backup.service` 備份主機設定。兩個服務及各自的 timer 必須事先存在，本倉庫不建立備份或保留政策。
- `pbs-report.py` 處理成功、失敗及已知的 PBS 離線略過紀錄；服務回報離線略過時不發訊息。PVE 通知 matcher 需允許 `vzdump` 的 info 和 error 至 Discord endpoint。
- 報告包含主機、狀態、開始及結束時間；VM／CT 報告也包含日誌中可解析的機器名稱及速度。資訊無法解析時顯示 `N/A` 或 `?`。速度是處理速度，並非網路吞吐量。
- 報告共用 PVE 的 `vzdump` 通知樣板，因此主機報告的標題也會出現 `vzdump`，內文標示 `HOST BACKUP`。PVE 原生備份通知可能另外發出，產生重複訊息。
- systemd 的 `ExecStopPost` 以 30 秒為上限並忽略報告錯誤，因此通知失敗不會改變備份結果；請另查日誌及確認 Discord 收到訊息。
- PBS 離線跳過後不會自動補跑。請定期在 PBS 檢查最後成功備份時間；沒有通知不代表已有新備份。

## 主機與倉庫的關係

兩台 PVE 各自保存 `/usr/local/sbin/pbs-report` 和 systemd drop-in。GitHub 是原始碼與維護文件，更新倉庫不會自動部署到任何主機。兩台 PVE 的 Node Notes 與 PBS Notes 記錄站點排程和存取入口；PBS 不會從倉庫拉取程式。不同機器的設定與套件更新可能造成行為差異。

## 從 Release 安裝與更新

**前提**：以 root 在 PVE 執行；先準備上述兩個備份服務、各自排程與通知端點。安裝器不建立這些服務，也不設定 PBS、Webhook 或排程。全新 PVE 不自帶這些服務；本倉庫目前沒有提供從零建立它們的步驟。

安排維護時段，先暫停所有可能啟動這兩個服務的 timer、cron 與人工作業，等待目前工作完成。安裝器只檢查當下狀態，不能阻止後續排程啟動。安裝及驗證完成後，恢復原本有啟用的排程。

1. 使用 [v0.1.0 Release](https://github.com/KarlSideProjects/pve-discord-backup-reports/releases/tag/v0.1.0) 指定的檔案及下列固定校驗值。下載、校驗後再執行，不要把網路腳本直接送進 shell。校驗值與檔案若來自同一 GitHub 帳號，無法獨立證明發行者身分。

   ```bash
   set -e
   workdir=$(mktemp -d)
   cd "$workdir"
   base=https://github.com/KarlSideProjects/pve-discord-backup-reports/releases/download/v0.1.0
   curl -fL --proto '=https' --tlsv1.2 -o install.sh "$base/install.sh"
   curl -fL --proto '=https' --tlsv1.2 -o report.tar.gz "$base/report.tar.gz"
   echo '5562edf0931609a519e8c7bd7d279ae7a0f73958524fc3e12399ae5f6cb3a542  install.sh' | sha256sum -c
   echo 'e93641469d01024eef8157aebcc70301e15f11650c83d44416174e2644004e70  report.tar.gz' | sha256sum -c
   sh install.sh report.tar.gz e93641469d01024eef8157aebcc70301e15f11650c83d44416174e2644004e70
   ```

2. 記錄輸出的 `Rollback directory`。安裝器先檢查依賴、服務、檔案與校驗碼，再保存原檔、安裝掛鉤並重新載入 systemd；失敗時嘗試回復。若顯示 `Rollback incomplete`，使用下方手動回復步驟。安裝器不執行備份或發送通知。
3. 確認服務狀態與掛鉤，恢復先前啟用的排程：

   ```bash
   systemctl show pbs-guarded-backup.service pve-host-config-backup.service -p Id -p LoadState -p ExecStopPost
   systemctl list-timers pbs-guarded-backup.timer pve-host-config-backup.timer
   ```

4. 在合適時間依本站備份規則進行測試，核對 journal、PBS 與 Discord。`systemctl start pve-host-config-backup.service` 或 `systemctl start pbs-guarded-backup.service` 會**實際寫入備份並可能清理舊備份**，不要在工作進行中重複執行。

   ```bash
   journalctl -u pbs-guarded-backup.service -n 100 --no-pager
   journalctl -u pve-host-config-backup.service -n 100 --no-pager
   ```

測試 VM 108 使用測試用空服務，驗證缺少服務時中止、安裝與模擬通知送達；這不代表真實 PBS 備份或還原已驗證。正式環境測試範圍見「安全與限制」。

## 還原報告程式

若更新後不正確，在 root shell 將下方路徑換成安裝前輸出的回復目錄。先確認該目錄包含保存的檔案或 `absent` 清單，避免選錯目錄。這會還原保存的檔案，並移除安裝前不存在的指定檔案。手動回復步驟尚未在 PVE 測試 VM 演練：

```bash
(
  set -e
  backup_dir=/root/pbs-report-rollback.請換成實際目錄
  test -d "$backup_dir" || { echo '回復目錄不存在'; exit 1; }
  if test -f "$backup_dir/absent"; then
    while IFS= read -r path; do rm -f "/$path"; done < "$backup_dir/absent"
  fi
  for path in usr/local/sbin/pbs-report etc/systemd/system/pbs-guarded-backup.service.d/20-discord-report.conf etc/systemd/system/pve-host-config-backup.service.d/20-discord-report.conf; do
    if test -f "$backup_dir/$path"; then cp -a "$backup_dir/$path" "/$path"; fi
  done
  systemctl daemon-reload
)
```

確認服務的 `ExecStopPost` 已回到原狀。若只要停止詳細報告，可移除兩個 `20-discord-report.conf` 並 reload；備份與原生 PVE 通知仍依原本設定執行。變動前先確認檔案內容與路徑，勿移除其他 drop-in。

## 安全與限制

- Webhook 網址、PBS 密碼、token、私人金鑰、原始完整設定及含敏感資訊的日誌不可提交。PVE 自行保存 Webhook 機密；GitHub 不負責散布憑證。
- 詳細報告依賴目前的 journal 文字格式、systemd invocation 與 PVE 內部通知樣板；升級 PVE 後應重新測試成功、失敗及 PBS 離線情況。
- 正式環境測過兩台主機備份成功通知、210 VM／CT 成功通知、207 模擬失敗與離線略過。207 完整 VM／CT 詳細報告尚待下一次正式備份確認。報告失敗可能無法透過同一通知管道告警。
- PBS Verify、GC 等作業不在這個報告程式的範圍。
