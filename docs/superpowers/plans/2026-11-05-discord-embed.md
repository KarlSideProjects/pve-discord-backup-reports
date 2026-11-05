# 結構化 Discord 報告實作計畫

**Goal:** 手機友善、逐 VM 欄位的 Discord Embed，維持既有通知路由。

**Architecture:** pbs-report.py 將日誌轉成結構化報告及符合 Discord 上限的 Embed；透過 PVE 通知 metadata 與專用模板發送，保留其他通知 fallback。先在 VM 108 證實 metadata 傳遞。

**Tech Stack:** Python 3、PVE Notifications、Discord Webhook、systemd。

**Spec:** docs/superpowers/specs/2026-11-05-discord-embed-design.md

- [ ] 先驗證測試 PVE metadata 與模板是否可傳送安全 JSON。
- [ ] 先寫失敗測試，再實作未知狀態、離線、欄位結構、限制及逃逸。
- [ ] 測試成功、失敗、未知、長報告和 Discord 實際送達；不觸碰正式 PBS。
- [ ] 同步操作文件與 backup.report 流程、獨立審查及 checker。
- [ ] 確認測試安全後再安排正式主機部署與驗證。
