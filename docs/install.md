# Adrian：安裝與維護

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

## 安裝與更新（部分已演練）

**前提**：在目標 PVE 使用 root shell；確認 Python 3、`journalctl`、`timeout` 和 PVE 的 `PVE::Notify` 可用。備份服務、PBS 離線檢查、PVE Discord Webhook 與 matcher 必須先行設定。本倉庫不提供憑證，也不保證可直接套用至其他備份服務或 PVE 版本。隔離的乾淨 Python 容器已實際執行自我測試及檔案安裝比對；該容器沒有 systemd 和 PVE::Notify，因此尚未完成全新 PVE 的整套演練。既有兩台 PVE 曾以相同內容安裝並測試通知。

1. 在目標主機的可信目錄取得私人倉庫。需先設定有讀取權限的 GitHub 驗證；不要把 token 放進網址、命令歷史或 Notes。

   ```bash
   git clone https://github.com/KarlSideProjects/pve-discord-backup-reports.git
   cd pve-discord-backup-reports
   ```

   執行自我測試並檢查現有版本。首次安裝時，本機檔案可能尚不存在：

   ```bash
   python3 pbs-report.py --self-test
   sha256sum pbs-report.py
   if test -f /usr/local/sbin/pbs-report; then sha256sum /usr/local/sbin/pbs-report; else echo "首次安裝：尚無本機副本"; fi
   ```

2. 寫入目標主機（會覆蓋現有報告程式及同名 drop-in；先保留原檔以便回復）：

   ```bash
   install -m 0755 pbs-report.py /usr/local/sbin/pbs-report
   install -D -m 0644 systemd/guest.conf /etc/systemd/system/pbs-guarded-backup.service.d/20-discord-report.conf
   install -D -m 0644 systemd/host.conf /etc/systemd/system/pve-host-config-backup.service.d/20-discord-report.conf
   systemctl daemon-reload
   systemctl show pbs-guarded-backup.service pve-host-config-backup.service -p Id -p ExecStopPost
   ```

3. 實際觸發合適的備份，確認 PVE task／journal 與 Discord 報告一致；勿在既有備份執行中重複啟動。主機備份可用 `systemctl start pve-host-config-backup.service`，VM／CT 可用 `systemctl start pbs-guarded-backup.service`。這些指令會實際寫入備份並可能執行保留清理。

4. 檢查排程及日誌：

   ```bash
   systemctl list-timers pbs-guarded-backup.timer pve-host-config-backup.timer
   journalctl -u pbs-guarded-backup.service -n 100 --no-pager
   journalctl -u pve-host-config-backup.service -n 100 --no-pager
   ```

## 還原報告程式

若更新後不正確，將先前保留的 `/usr/local/sbin/pbs-report` 和兩個 drop-in 還原，再執行 `systemctl daemon-reload`。若只要停止詳細報告，可移除兩個 `20-discord-report.conf` 並 reload；備份與原生 PVE 通知仍依原本設定執行。變動前先確認檔案內容與路徑，勿移除其他 drop-in。

## 安全與限制

- Webhook 網址、PBS 密碼、token、私人金鑰、原始完整設定及含敏感資訊的日誌不可提交。PVE 自行保存 Webhook 機密；GitHub 不負責散布憑證。
- 詳細報告依賴目前的 journal 文字格式、systemd invocation 與 PVE 內部通知樣板；升級 PVE 後應重新測試成功、失敗及 PBS 離線情況。
- 正式環境測過兩台主機備份成功通知、210 VM／CT 成功通知、207 模擬失敗與離線略過。207 完整 VM／CT 詳細報告尚待下一次正式備份確認。報告失敗可能無法透過同一通知管道告警。
- PBS Verify、GC 等作業不在這個報告程式的範圍。
