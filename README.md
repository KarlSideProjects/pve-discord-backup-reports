# PVE 備份 Discord 報告

自動把 PVE 的備份結果整理成表格，送到 Discord。

```mermaid
flowchart LR
  A["PVE 定時備份"] --> B["PBS 儲存備份"]
  A --> C["整理備份報告"]
  C --> D["PVE 通知設定"]
  D --> E["Discord 備份通知"]
```

報告包含 **成功或失敗、開始與結束時間、可取得的處理速度**。PBS 離線時會跳過，不發通知，也不會自動補跑。

## Adrian：安裝與維護

```mermaid
flowchart LR
  A["準備 PVE 備份服務<br/>及 Discord Webhook"] --> B["取得私人倉庫"]
  B --> C["測試並安裝報告程式"]
  C --> D["觸發備份並確認通知"]
```

👉 [安裝、更新、驗證與回復步驟](docs/install.md)

🔎 [程式流程與追蹤範圍](docs/flows/README.md)

兩台 PVE 各執行自己的程式；**GitHub 更新不會自動部署**。PBS 只儲存備份，不執行本程式。安裝指引中的完整乾淨安裝流程仍待演練。

> Webhook 網址、密碼與金鑰請留在 PVE，勿提交至 GitHub。
