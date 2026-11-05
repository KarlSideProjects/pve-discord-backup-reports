# 報告邊界

- 現有兩個備份服務各自執行報告 drop-in；它們的設定、排程、PBS 探測、保留與備份實作不由本倉庫管理。
- 報告只讀取 systemd 本次 invocation 的 journal 與服務結果。已知的 PBS 離線略過不發送。其餘完成或失敗會嘗試產生報告；讀取 journal、程式處理、通知呼叫失敗或逾時可能無法送達。報告透過 PVE Notifications matcher 與 Webhook 路由；Discord 是否送達依賴外部服務及設定。
- 資料缺漏時顯示 N/A 或不確定，處理速度不代表網路吞吐量。成功通知不代表備份已驗證或可還原。
- drop-in 對報告設 30 秒上限並忽略報告程序錯誤；報告失敗不應改變備份 service 結果。
- PVE 外部服務、Webhook、matcher、PBS 和 Discord 屬部署依賴，需透過實際環境另行驗證。本機自我測試不能證明訊息送達。
