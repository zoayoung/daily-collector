# 05: 全链路验收与 CI 冒烟

**What to build:** 用真实或夹具数据完整跑通采集→分析→整理→校验→打分→渲染，确认读者拿到的日报满足新口径；并在临时分支用真实 GitHub Actions 验证自动运行的跳过与覆盖路径。这是交付门槛，不引入新的测试 seam。

**Blocked by:** 04: 整理与渲染：定稿 10–15 条、移除新进展（contract）

**Status:** ready-for-agent

- [x] 本地全链路产物通过校验与打分；日报 10–15 条、无重复窗口内项目、无「新进展」行。
- [x] 入榜集的候选数、可入榜数、重复剔除数自洽，并与日报数量对得上。
- [x] token 报告与用量产物数值一致。
- [x] 旧的无 `stats` 入榜集仍通过 `--all` 校验。
- [x] CI 冒烟覆盖 `force=false` 跳过（退出 0、不产生新提交）与 `force=true` 覆盖（重新采集并提交日报、token 报告与当日入榜集）。
- [x] CI 失败时上传当日工作目录 artifact，不提交半成品，最后一份已发布日报保持不变。

## Comments

- 2026-10-22 本地全链路验收通过：新增 `tests/test_end_to_end.py`，用 FixtureServer 动态回放 51 个候选（50 个可入榜 + 1 个 30 天窗口内项目），跑通 collect → analyze（50 条）→ organize（12 条）→ validate → score → 按 spec 模板渲染；断言日报 12 条、窗口内项目零出现、无「新进展」行、`stats.candidates - dropped = eligible`、`eligible >= 入榜数 >= 日报条数`、旧无 `stats` 入榜集仍过 `--all`、token 报告与 `tokens.json` 各自自洽且同一 run 逐字段一致。
- 本地命令：`uv run python -m unittest discover -s tests -t .`（55 项通过）、`uv run ruff check scripts tests`（通过）、`uv run python scripts/validate.py --all`（通过）。
- CI 工作流静态验收（`.github/workflows/daily-knowledge.yml`）：`force=false` 时 guard 置 `skip=true`，`daily` job 不运行、退出 0、不产生提交；`force=true` 时先清理当日日报与 collect/analyze/organize/score 再重跑；失败步骤 `if: failure()` 上传 `work/<日期>/`；提交仅包含 `daily-knowledge` 与 `work/<日期>/collect.json`，失败不提交半成品。
- 2026-10-22 真实 GitHub Actions 冒烟通过（临时分支 `ci-smoke`，已配置 `OC_GO_API_KEY`）：
  - `force=true`：<https://github.com/zoayoung/daily-collector/actions/runs/39683609127> 成功，回写提交 `86b5e9a`，只改 `daily-knowledge/2026-10-22.md`、`daily-knowledge/tokens/2026-10-22.md`、`work/2026-10-22/collect.json`。
  - `force=false`：<https://github.com/zoayoung/daily-collector/actions/runs/39684378125> 成功；`guard` 跳过、`daily` 未运行，远端 head 保持 `86b5e9a`，无新提交。
  - 失败 artifact：历史失败运行 <https://github.com/zoayoung/daily-collector/actions/runs/39664550828> 的 artifact `work-2026-10-22-1` 存在，日报未被改写。
- CI 生成日报复核：12 条、窗口内重复 0 条、无「新进展」行；`stats.candidates=800`、`eligible=776`、`dropped_recent_duplicates=24`，自洽。
