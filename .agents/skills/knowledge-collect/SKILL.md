---
name: knowledge-collect
description: 知识采集系统「采集」阶段的流程技能。主代理委派 knowledge-collect 子代理执行当日采集时加载：用 GitHub 搜索 API 拉候选、逐个算出「今日新增 star」（本地历史差分优先、官方 star 历史兜底），按增量排序取前 15–20，落盘 work/YYYY-MM-DD/collect.json。
allowed-tools: Read(AGENTS.md), Read(.scratch/knowledge-daily/topics.md), Read(.scratch/knowledge-daily/spec.md), Read(work/**), Glob(work/**), Write(work/**), Edit(work/**), WebFetch(domain:api.github.com), TodoWrite
---

# 知识采集技能（采集阶段）

## 使用场景

主代理委派采集阶段时加载：当日尚无 `work/YYYY-MM-DD/collect.json`，或用户选择「重新采集并覆盖」。你只做原样抓取、算增量与落盘；主题取舍、去重判断、新进展核查与写作属于分析阶段，不在这里做。

## 输入

- 委派消息中的日期（`YYYY-MM-DD`）与产物路径。
- 只读文件：`.scratch/knowledge-daily/spec.md`（采集口径与数据契约节）、`.scratch/knowledge-daily/topics.md`（六主题与关键词）。
- 只读历史：`work/**/collect.json`（此前各日的采集产物，供今日新增 star 的本地差分）。
- 无前置产物。

## 执行步骤

1. **读取口径**：读 spec 的采集与数据契约节、`.scratch/knowledge-daily/topics.md`。完成标志：能列出候选查询、今日新增 star 的三种取值来源与 15–20 条选取规则。
2. **建本地基线**：读 `work/**/collect.json`，为每个 repo 记下**日期早于今日的最近一次** `stars_total` 及其基线日期。完成标志：输出一份 `repo → 基线 star（及日期）` 的对照。
3. **拉候选集**：调搜索 API `https://api.github.com/search/repositories?q=pushed:%3E%3D{T-1d}+stars:%3E=100&sort=stars&order=desc&per_page=100`（`{T-1d}` 为委派日期减 1 天）。取首页前 100 条。完成标志：拿到候选列表；调用失败即按失败模式判阶段失败。
4. **算今日新增 star**：对每个候选依次赋值（口径统一为当日新增）——
   - 有**上一自然日**基线：`stars_today = stars_total − 基线`，`stars_today_source=local_diff`；
   - 无上一自然日基线：按 `stars_total` 降序依次调 `https://api.github.com/repos/{owner}/{repo}/stargazers/history`，取覆盖当日的增量（当日值尚未出现时取最近一日），`stars_today_source=star_history`；此类调用总量 ≤20 次/轮；
   - 两者都不可得：`stars_today=null`、`stars_today_source=null`。
   完成标志：每个候选都有来源标注；单个 star_history 失败记 `gaps` 并记 null，不中断。
5. **排序选取**：丢弃 `stars_today=null` 的候选，其余按 `stars_today` 降序取前 15–20 条（不足 15 按实际数量）。
6. **组装落盘**：按「输出契约」组装 JSON 并逐项自检，通过后写 `work/YYYY-MM-DD/collect.json`。
7. **回复**：按「输出契约」的回复模板报告结果。

## 输出契约

产物 `work/YYYY-MM-DD/collect.json`（UTF-8），字段以 spec「collect.json」节为准，其中：

- `date` 为委派日期；`collected_at` 为本地时间（UTC+8，`YYYY-MM-DD HH:mm`）。
- `github[]`：字段齐全（full_name/url/description/language/stars_total/stars_today/stars_today_source/forks/created_at/pushed_at）、同 repo 无重复、按 `stars_today` 降序、条数 15–20。
- `stars_today` 只来自本地差分或官方 star 历史；两者都拿不到记 null 并在 `gaps` 说明，绝不推测、编造或凑数。
- `gaps[]`：如实记录抓取异常与字段缺失（含未纳入的候选数量、star_history 调用次数）。
- 每个字段值都来自 API 返回；不推测、不编造、不凑数。

写文件前自检：JSON 可解析；上述各项逐条通过；未触碰 `work/` 之外任何路径。

最终回复：

- 成功：`✅ 采集完成；产物：work/YYYY-MM-DD/collect.json；候选 N，入榜 M；新增 star 来源：本地差分 X、star 历史 Y；gaps：有/无`
- 失败：`❌ 采集失败；原因：…；已落盘：无 / work/YYYY-MM-DD/collect.partial.json；建议：…`

## 失败模式

- 搜索 API 失败：阶段失败，不写正式 collect.json。
- 单个 star_history 失败：记 `gaps` 并把该条 `stars_today` 记 null，继续其余候选。
- 入榜不足 15 条：按实际数量输出并在 `gaps` 说明。
- 中途失败：已抓数据可写 `work/YYYY-MM-DD/collect.partial.json` 供人工诊断；主代理与续跑不视其为完成。

## 正反向自测

- 正向：按输出契约自检清单逐项核对并确认 JSON 可解析后，才算完成。
- 反向：搜索 API 不可达、拿不到足够带增量的候选而无法成榜时，不写正式 collect.json（最多留 partial），并按失败模板返回。

## 权限边界

- 允许：读 `AGENTS.md`、`.scratch/knowledge-daily/topics.md`、spec、`work/`（含历史 collect.json）；写仅 `work/**`（创建/覆盖当日 collect.json 与 partial）；WebFetch 仅限 api.github.com；TodoWrite。
- 硬边界：不写 `work/` 之外任何路径、不改既有文件、不引入 spec 之外的采集源或域名、不询问用户。
