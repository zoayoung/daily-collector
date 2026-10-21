# 06: ci-smoke 真实冒烟并合并 main

**What to build:** 先在公开仓库建立 `main` 基线，再用临时 `ci-smoke` 分支真实触发流水线：第一次强制覆盖跑通完整的采集、分析、整理、渲染与回写，第二次不强制验证当日跳过。修复所有暴露的问题直到两次都符合预期，然后把经过验证的分支合并到 `main`，确认每日定时任务已注册。完成后仓库可直接依赖定时任务产出日报。

**Blocked by:** 05（外部前置已满足：`OC_GO_API_KEY` 已配置）

**Status:** ready-for-human

- [ ] `main` 作为默认分支建立，仓库可正常推送与拉取。
- [ ] 在 `ci-smoke` 分支以 `force=true` 触发，工作流全绿，回写日报、token 报告与采集产物。
- [ ] 同一天以 `force=false` 再次触发，工作流跳过且不产生新提交。
- [ ] 失败路径能上传中间产物、不覆盖最后一份已发布日报。
- [ ] 合并到 `main` 后工作流保持绿色，定时任务可见。
- [ ] 全程日志与提交中不出现模型密钥明文。

## Comments

- 2026-10-22：工单 01–05 已实现并合并到集成分支 `feat/knowledge-daily-v3`；本工单仍未开始，原因是当前环境缺少外部前置：
  - `https://github.com/zoayoung/daily-collector` 可访问但为空仓库，没有 `main` 基线；
  - 本机没有可用的推送凭证：spec 指定的 `~/.ssh/git` 不存在，现有 SSH key 被 GitHub 拒绝（`Permission denied (publickey)`），进程环境与 `.env` 均无 `GITHUB_TOKEN`；
  - 无法配置仓库 Secret `OC_GO_API_KEY`，也无法触发真实 `workflow_dispatch`。
- 解除阻塞所需人工动作：提供可推送的仓库凭证（SSH key 或 token）与已配置 `OC_GO_API_KEY` 的仓库，然后按 spec「CI 冒烟」在 `ci-smoke` 分支跑通 `force=true` / `force=false` 与失败 artifact 三条路径，绿后合并 `main`。
