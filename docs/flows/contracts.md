# 報告邊界

- 現有兩個備份服務各自執行報告 drop-in；它們的設定、排程、PBS 探測、保留與備份實作不由本倉庫管理。
- 報告只讀取 systemd 本次 invocation 的 journal 與服務結果。已知的 PBS 離線略過不發送。其餘完成或失敗會嘗試產生報告；讀取 journal、程式處理、通知呼叫失敗或逾時可能無法送達。報告透過 PVE Notifications matcher 與 Webhook 路由；Discord 是否送達依賴外部服務及設定。
- 資料缺漏時顯示 N/A 或資料不足，並用 error 路由以避免被 info/error matcher 漏掉；處理速度不代表網路吞吐量。報告時間不是備份結束時間。成功通知不代表備份已驗證或可還原。Embed 超出預算時優先保留失敗項並標示省略；Webhook 對其他通知保留文字 fallback。
- 主機報告預期 `etc` 與 `pve-config` 兩個封存的速度和結束時間；任一缺少時標示資料不足。
- drop-in 對報告設 30 秒上限並忽略報告程序錯誤；報告失敗不應改變備份 service 結果。
- PVE 外部服務、Webhook、matcher、PBS 和 Discord 屬部署依賴，需透過實際環境另行驗證。本機自我測試不能證明訊息送達。

- Release 安裝器驗證指定壓縮檔 SHA-256 與限定內容，先檢查服務依賴和狀態，保存三個目標的原狀後安裝；失敗時嘗試回復。安裝不啟動備份、不建立服務、排程或 Webhook。管理員須先暫停排程並阻止人工啟動，以免安裝時發生競態。

- 結構化 payload 經 report_json metadata 與專用 Webhook 樣板傳遞；來源必須為可信任的報告程式，不得將不可信的原始 JSON 直接寫入 metadata。allowed_mentions 停用提及。
