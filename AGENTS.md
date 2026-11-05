# 專案協作規則

## 流程文件
修改已納入功能前，閱讀 `docs/flows/README.md`、`docs/flow-manifest.json` 的相關功能及依賴、流程圖和 `docs/flows/contracts.md`，並回報影響的 feature ID。從來源確認未知基線。功能範圍改變時重新閱讀相關內容。

本專案以交付的 staged candidate 為檢查邊界，base 必須是變更前的可信 commit，不能用已提交 candidate 與自身比較。工作進行中可保留未完成狀態；交付前同步受影響的流程與契約，執行 `python3 tools/flow-docs/flow_checker.py explain --root . --base <base> --staged`，使用 packet 提供完整上下文並取得所需獨立審查，再以相同 base 執行 `python3 tools/flow-docs/flow_checker.py check --root . --base <base> --staged`。缺少上下文或審查不得宣稱完成。不要將 checker 當成語意驗證或遠端合併保護。

技術文件依 technical-writing 技能撰寫；操作步驟依 writing-runbooks 技能維護。
