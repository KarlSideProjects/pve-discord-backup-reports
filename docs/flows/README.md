# 流程索引

| 功能 | 流程 | 契約 | 來源 |
| --- | --- | --- | --- |
| `backup.report` | [報告流程](backup.report.mmd) | [報告邊界](contracts.md) | `install.sh`, `templates/discord-webhook.hbs`, `pbs-report.py`, `systemd/guest.conf`, `systemd/host.conf` |

追蹤範圍為安裝器、報告程式、Webhook 樣板及兩個 systemd drop-in。PVE 的備份服務、timer、離線守門程式、PVE Notifications 設定、PBS 和 Discord 均在範圍外；這些邊界的運作與端到端送達需另外驗證。

交付前使用真實變更前 commit 作 base，執行 `python3 tools/flow-docs/flow_checker.py explain --root . --base <base> --staged`，產生受影響功能的 packet 並取得獨立審查，再執行相同 base 的 `check --staged`。checker 僅檢查結構與審查聲明，不能證明語意或審查者身分。初始導入尚未設定自動 AI runner、CI 或遠端合併保護。
