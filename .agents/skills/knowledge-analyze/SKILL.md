---
name: knowledge-analyze
description: 知识采集系统「分析」阶段的流程技能。主代理委派 knowledge-analyze 子代理执行当日分析、或打回低分条目要求重写时加载：只做项目内容分析——按 topics.md 打主题标签、按 spec 的时间窗口去重、核查新进展、逐条写分析要点与评价，产出 work/YYYY-MM-DD/analyze.json。
allowed-tools: Read(AGENTS.md), Read(.scratch/knowledge-daily/topics.md), Read(.scratch/knowledge-daily/spec.md), Read(work/**), Read(daily-knowledge/**), Write(work/**), Edit(work/**), Glob, Grep, WebFetch(domain:github.com), TodoWrite
---

# 知识分析技能（分析阶段）

## 使用场景

主代理委派分析阶段时加载，两种情形：

- 首次分析：当日 `collect.json` 已存在而 `analyze.json` 未产出。
- 打回重写：主代理带着「低分条目清单」再次委派，只重写这些条目的分析要点。

你只做**项目内容分析**：打标签、去重、核查新进展、写要点与评价。选取多少条、排序、润色成稿与写日报都不在这里做。

## 输入

- 委派消息中的日期与产物路径。
- `work/YYYY-MM-DD/collect.json`（必需；缺失或不可解析时立即失败）。
- 只读：spec（数据契约与打标签口径节）、`.scratch/knowledge-daily/topics.md`、`daily-knowledge/` 下全部历史 md（时间去重依据，不建索引）。
- 打回模式下另有：低分条目清单（含五维得分、命中空洞词、低分原因）。没有清单即为首次分析。

## 执行步骤

1. **读取**：读 collect.json、spec、topics.md。完成标志：collect.json 可解析，打标签口径已掌握。
2. **建历史对照**：读 `daily-knowledge/` 下全部 md，得到每个 repo 的上次出现日期。完成标志：daily-knowledge/ 下每个 md 都已扫过。
3. **打标签与去重**：按 topics.md 为每个 github 条目分配 `themes`（数组，可多主题，无命中为空数组）；spec 定义的时间窗口内出现过的 repo 须有新进展才保留（判断不了视为无进展），窗口外历史照常输出并标 `repeat`；剔除数记入 `stats.dropped_recent_duplicates`。完成标志：每条保留/剔除都有依据，`themes` 均非缺失。
4. **写分析要点**：逐条写 `core`（项目做了什么、关键事实与理由）与 `why`（一句评价，附是否跟进/怎么用的建议）。素材补足：仓库描述过短或不明时才抓 README，且只读约定范围；素材补抓总量受 spec 限制，失败用已有字段概括并记 `gaps`。完成标志：每条都有言之有物的 core 与 why。
5. **组装概览之外的部分**：组装 `stats`、`gaps`。不写 `rank`、不写 `overview`、不做选取——这些属于整理阶段。
6. **组装落盘**：按「输出契约」自检后写 `work/YYYY-MM-DD/analyze.json`；按模板回复。

**打回模式**：读现有 `analyze.json`，只替换清单中条目的 `core` 与 `why`（必要时补抓素材），其余条目、`themes`、`repeat`、`stats` 保持不变；不新增条目、不复活已被剔除的条目。写完同样按输出契约自检。

## 输出契约

产物 `work/YYYY-MM-DD/analyze.json`（UTF-8），字段以 spec「analyze.json」节与 `schemas/analyze.schema.json` 为准，其中：

- `date` 为委派日期。
- `github`：collect 全部字段 + `themes`（数组）+ `repeat` + `core` + `why`；条数与 collect 中去重后保留的条目一致，按 `stars_today` 降序。
- `stats`：`{ github_count, dropped_recent_duplicates }`，`github_count` 等于 `github` 条数。
- `gaps` 如实记录素材抓取失败等异常。
- 不含 `rank`、`overview`、`dropped_by_organize`。

写文件前自检：JSON 可解析；字段不越界；`repeat.last_seen` 在历史中真实存在；未写 `work/` 之外任何路径。

最终回复：

- 成功：`✅ 分析完成；产物：work/YYYY-MM-DD/analyze.json；GitHub N 条；命中主题 T 个；剔除无新进展 D 条；gaps：有/无`
- 打回成功：`✅ 分析重写完成；重写 K 条；产物：work/YYYY-MM-DD/analyze.json`
- 失败：`❌ 分析失败；原因：…；已落盘：无 / work/YYYY-MM-DD/analyze.partial.json；建议：…`

## 失败模式

- collect.json 缺失或不可解析：立即失败，不猜数据、不自行抓原始榜。
- 打回模式找不到清单中的条目：按失败返回，不自行替换为其他条目。
- 新进展核查失败：保守视为无进展（不计入失败）。
- 单条素材抓取失败：用已有字段概括该条，`gaps` 记「N 条素材抓取失败」。
- 写入失败：按失败模板返回。

## 正反向自测

- 正向：按输出契约自检清单逐项核对并确认 JSON 可解析后，才算完成。
- 反向：前置缺失或产不出合法 JSON 时，不写正式 analyze.json（最多留 partial），并按失败模板返回。

## 权限边界

- 允许：读 `AGENTS.md`、topics.md、spec、`work/`、`daily-knowledge/`；写仅 `work/**`；Glob、Grep、WebFetch（仅 github.com 的仓库页/README）、TodoWrite。
- 硬边界：不写 `daily-knowledge/`、不修改 collect.json、不引入 topics.md 之外的主题、不决定入选条数与排序、`repeat` 与新进展只依据真实历史、不询问用户。
