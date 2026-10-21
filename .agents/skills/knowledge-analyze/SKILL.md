---
name: knowledge-analyze
description: 知识采集系统「分析」阶段的流程技能。主代理委派 knowledge-analyze 子代理执行当日分析、或打回低分条目要求重写时加载：只做项目内容分析——按项目内容自由打标签、为重复窗口外再次出现的项目标 last_seen、逐条写分析要点与评价，产出 work/YYYY-MM-DD/analyze.json。
allowed-tools: Read(AGENTS.md), Read(.scratch/knowledge-daily/spec.md), Read(work/**), Read(daily-knowledge/**), Write(work/**), Edit(work/**), Glob, Grep, WebFetch(domain:github.com), TodoWrite
---

# 知识分析技能（分析阶段）

## 使用场景

主代理委派分析阶段时加载，两种情形：

- 首次分析：当日 `collect.json` 已存在而 `analyze.json` 未产出。
- 打回重写：主代理带着「低分条目清单」再次委派，只重写这些条目的分析要点。

你只做**项目内容分析**：打标签、标注重复、写要点与评价。按重复窗口剔除条目由采集与校验负责，选取多少条、排序、润色成稿与写日报都不在这里做。

## 输入

- 委派消息中的日期与产物路径。
- `work/YYYY-MM-DD/collect.json`（必需；缺失或不可解析时立即失败）。
- 只读：spec（数据契约、打标签口径与重复窗口节）、`daily-knowledge/` 下全部历史 md（重复标记依据，不建索引）。
- 打回模式下另有：低分条目清单（含五维得分、命中空洞词、低分原因）。没有清单即为首次分析。

## 执行步骤

1. **读取**：读 collect.json 与 spec。完成标志：collect.json 可解析，打标签口径已掌握。
2. **建历史对照**：读 `daily-knowledge/` 下全部 md，得到每个 repo 最近一次发布日期。完成标志：daily-knowledge/ 下每个 md 都已扫过。
3. **打标签与标注重复**：处理 collect.json 的全部条目，不按重复窗口自行剔除。按项目内容为每条自由分配 `themes`（非空标签数组，数量口径见 spec『实现决策 · 标签口径』；完全无法归类时用空数组表示「未打标签」）。仅当项目在重复窗口外再次出现时写 `repeat.last_seen`，值等于历史中最近一次发布日期；无历史或窗口内记录不作为 `repeat` 依据；不写 `new_progress`。完成标志：全部条目都有 `themes`，每个 `repeat` 要么为 null、要么带与历史一致的 `last_seen`。
4. **写分析要点**：逐条写 `core`（项目做了什么、关键事实与理由）与 `why`（一句评价，附是否跟进/怎么用的建议）。素材补足：仓库描述过短或不明时才抓 README，且只读约定范围；素材补抓总量受 spec 限制，失败用已有字段概括并记 `gaps`。完成标志：每条都有言之有物的 core 与 why。
5. **组装概览之外的部分**：组装 `stats`、`gaps`。`stats.dropped_recent_duplicates` 沿用 collect.json 的统计，collect 无 `stats` 时按 spec『统计透传』处理。不写 `rank`、不写 `overview`、不做选取——这些属于整理阶段。
6. **组装落盘**：按「输出契约」自检后写 `work/YYYY-MM-DD/analyze.json`；按模板回复。

**打回模式**：读现有 `analyze.json`，只替换清单中条目的 `core` 与 `why`（必要时补抓素材），其余条目、`themes`、`repeat`、`stats` 保持不变；不新增或删除条目。写完同样按输出契约自检。

## 输出契约

产物 `work/YYYY-MM-DD/analyze.json`（UTF-8），字段以 spec「analyze.json」节与 `schemas/analyze.schema.json` 为准，其中：

- `date` 为委派日期。
- `github`：collect 全部条目与字段 + `themes`（数组）+ `repeat` + `core` + `why`；条数与 collect 条目一致，按 `stars_today` 降序。
- `repeat`：仅为重复窗口外再次出现的项目写 `{"last_seen": "YYYY-MM-DD"}`；不写 `new_progress`。
- `stats`：`{ github_count, dropped_recent_duplicates }`，`github_count` 等于 `github` 条数，`dropped_recent_duplicates` 沿用 collect.json。
- `gaps` 如实记录素材抓取失败等异常。
- 不含 `rank`、`overview`、`dropped_by_organize`。

写文件前自检：JSON 可解析；字段不越界；collect 全部条目都在；`repeat.last_seen` 在历史中真实存在且为最近一次发布日期；未写 `new_progress`；未写 `work/` 之外任何路径。

最终回复：

- 成功：`✅ 分析完成；产物：work/YYYY-MM-DD/analyze.json；GitHub N 条；标签 M 个；重复标记 R 条；gaps：有/无`
- 打回成功：`✅ 分析重写完成；重写 K 条；产物：work/YYYY-MM-DD/analyze.json`
- 失败：`❌ 分析失败；原因：…；已落盘：无 / work/YYYY-MM-DD/analyze.partial.json；建议：…`

## 失败模式

- collect.json 缺失或不可解析：立即失败，不猜数据、不自行抓原始榜。
- 打回模式找不到清单中的条目：按失败返回，不自行替换为其他条目。
- 重复历史读取失败：按「无重复」保守处理并在 `gaps` 说明，不中断分析。
- 单条素材抓取失败：用已有字段概括该条，`gaps` 记「N 条素材抓取失败」。
- 写入失败：按失败模板返回。

## 正反向自测

- 正向：按输出契约自检清单逐项核对并确认 JSON 可解析后，才算完成。
- 反向：前置缺失或产不出合法 JSON 时，不写正式 analyze.json（最多留 partial），并按失败模板返回。

## 权限边界

- 允许：读 `AGENTS.md`、spec、`work/`、`daily-knowledge/`；写仅 `work/**`；Glob、Grep、WebFetch（仅 github.com 的仓库页/README）、TodoWrite。
- 硬边界：不写 `daily-knowledge/`、不修改 collect.json、不引用固定主题表或预设白名单、不自行按重复窗口剔除条目、不决定入选条数与排序、不写 `new_progress`、`repeat` 只依据真实历史、不询问用户。
