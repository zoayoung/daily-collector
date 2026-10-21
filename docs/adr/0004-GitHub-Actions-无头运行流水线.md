# GitHub Actions 无头运行流水线

日报需要每天稳定产出，人工触发会因出差、忘记或环境差异而断档。现在由 GitHub Actions 在每日 00:00 UTC（08:00 UTC+8）运行与本地相同的采集→分析→整理→渲染流程，也保留 `workflow_dispatch` 手动触发与 `force` 覆盖。

工作流锁定 `@opencode/cli@2.0.26` 与 `oc-go/deepseek-v4.1-flash`，把 provider 与默认模型写进仓库级 `opencode.json`，密钥只从 Secret `OC_GO_API_KEY` 注入；采集与回写共用 Actions 自带 `GITHUB_TOKEN`。同日已存在日报且未强制时跳过并成功退出；`force=true` 先清理工作区当日阶段产物，再按重新采集覆盖。提交范围仅限 `daily-knowledge/` 与当日 `work/<日期>/collect.json`，无变更不空提交。

失败不自动重试、不提交半成品，只把 `work/<日期>/` 上传为 artifact，远端最后一份日报保持不变。同一 workflow 使用单一并发组，避免定时与手动触发重叠；代价是手动触发在定时任务运行时只能排队，且 cron 在高峰期可能延迟。锁定 opencode 版本也意味着升级需要人工验证 provider 与 CLI 参数后再改，换来的是 runner 上行为可复现、不会因上游自动升级而漂移。
