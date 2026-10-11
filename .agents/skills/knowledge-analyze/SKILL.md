---
name: knowledge-analyze
description: 知识采集系统「分析」阶段的流程技能。主代理委派 knowledge-analyze 子代理执行当日分析时加载：按 .scratch/knowledge-daily/topics.md 给项目打主题标签、做 30 天时间去重、核查新进展，逐条生成含评价的初稿（核心内容 ≤100 汉字），产出 work/YYYY-MM-DD/analyze.json。
allowed-tools: Read(AGENTS.md), Read(.scratch/knowledge-daily/topics.md), Read(.scratch/knowledge-daily/spec.md), Read(work/**), Read(output/**), Write(work/**), Edit(work/**), Glob, Grep, WebFetch(domain:github.com), TodoWrite
---

# 知识分析技能（分析阶段）

## 使用场景

主代理委派分析阶段时加载：当日 `collect.json` 已存在而 `analyze.json` 未产出，或用户要求重新分析。你把采集产物转为「打标签、去重、带初稿文字」的分析产物；不抓新榜单、不写日报。

## 输入

- 委派消息中的日期与产物路径。
- `work/YYYY-MM-DD/collect.json`（必需；缺失或不可解析时立即失败）。
- 只读：spec（数据契约与主题打标签口径节）、`.scratch/knowledge-daily/topics.md`、`output/` 下全部历史 md（时间去重依据，不建索引）。

## 执行步骤

1. **读取**：读 collect.json、spec、`.scratch/knowledge-daily/topics.md`。完成标志：collect.json 可解析，六主题打标签口径已掌握。
2. **建历史对照**：读 `output/` 下全部 md，得到每个 repo 的上次出现日期。完成标志：output/ 下每个 md 都已扫过。
3. **打标签与去重**：按 `.scratch/knowledge-daily/topics.md` 为每个 github 条目分配 `themes`（数组，可多主题，无命中为空数组）；30 天窗口内出现过的 repo 须有新进展才保留（判断不了视为无进展），更早历史照常输出并标 `repeat`；剔除数记入 `stats.dropped_recent_duplicates`。完成标志：每条保留/剔除都有依据，`themes` 均非缺失。
4. **生成初稿**：逐条写 `core`（≤100 个汉字：承载理由与支撑事实，不计英文单词与数字）与 `why`（一句评价，附是否跟进/怎么用的建议）。素材补足：仓库描述过短或不明时才抓 README，且**只读前 500 汉字（中文）或前 500 词（英文）；若该处句子/段落被截断则扩到 1000**；素材补抓总量 ≤20 次/天，失败用已有字段概括并记 `gaps`。完成标志：每条都有合规的 core 与 why。
5. **组装概览**：写 `overview.lead`（今日一句总述）与 `overview.themes`（当日命中的每个主题一句要点，0 命中省略）。
6. **组装落盘**：组装 `stats`、`gaps`，按「输出契约」自检后写 `work/YYYY-MM-DD/analyze.json`；按模板回复。

## 输出契约

产物 `work/YYYY-MM-DD/analyze.json`（UTF-8），字段以 spec「analyze.json」节为准，其中：

- `date` 为委派日期。
- `github`：collect 全部字段 + `themes`（数组）+ 连续 `rank` + `repeat` + `core` + `why`；15–20 条、按 `stars_today` 降序。
- `core`：≤100 个汉字（不计英文单词与数字）；`why`：一句评价，附理由与建议（建议并入 why）。
- `overview`：`lead` 一句 + `themes[]`（`{name, note}`，只含命中主题）。
- `repeat.last_seen` 必须真实存在于 `output/` 历史；`new_progress` 仅 30 天窗口内条目可写。
- `stats`：`{ github_count, dropped_recent_duplicates }`，`github_count` 等于 `github` 条数。
- `gaps` 如实记录素材抓取失败等异常。

写文件前自检：JSON 可解析；上述各项逐条通过；未写 `work/` 之外任何路径。

最终回复：

- 成功：`✅ 分析完成；产物：work/YYYY-MM-DD/analyze.json；GitHub N 条；命中主题 T 个；剔除 30 天内无新进展 D 条；gaps：有/无`
- 失败：`❌ 分析失败；原因：…；已落盘：无 / work/YYYY-MM-DD/analyze.partial.json；建议：…`

## 失败模式

- collect.json 缺失或不可解析：立即失败，不猜数据、不自行抓原始榜。
- 新进展核查失败：保守视为无进展（不计入失败）。
- 单条素材抓取失败：用已有字段概括该条，`gaps` 记「N 条素材抓取失败」。
- 写入失败：按失败模板返回。

## 正反向自测

- 正向：按输出契约自检清单逐项核对并确认 JSON 可解析后，才算完成。
- 反向：前置缺失或产不出合法 JSON 时，不写正式 analyze.json（最多留 partial），并按失败模板返回。

## 权限边界

- 允许：读 `AGENTS.md`、`.scratch/knowledge-daily/topics.md`、spec、`work/`、`output/`；写仅 `work/**`；Glob、Grep、WebFetch（仅 github.com 的仓库页/README）、TodoWrite。
- 硬边界：不写 `output/`、不修改 collect.json、不引入 `.scratch/knowledge-daily/topics.md` 之外的主题、`repeat` 与新进展只依据真实历史、全量读 README 只限约定范围、不询问用户。
