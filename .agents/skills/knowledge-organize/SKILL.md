---
name: knowledge-organize
description: 知识采集系统「整理」阶段的流程技能。主代理委派 knowledge-organize 子代理执行日报定稿时加载（analyze.json 已存在）：从分析结果中定稿当日入选条目，润色 core 与 why、写 rank 与 overview，产出 work/YYYY-MM-DD/organize.json。不写日报、不抓取网页、不自行回改评分。
allowed-tools: Read(AGENTS.md), Read(.scratch/knowledge-daily/topics.md), Read(.scratch/knowledge-daily/spec.md), Read(work/**), Read(daily-knowledge/**), Write(work/**), Edit(work/**), TodoWrite
---

# 知识整理技能（整理阶段）

## 使用场景

主代理委派整理阶段时加载：当日 `analyze.json` 已存在而 `organize.json` 未产出；或打分打回后需要重新定稿。你负责**定稿**：选多少条进日报、怎么排序、文字怎么润色、概览怎么写。不做标签判定、不做去重判断、不抓网页。

## 输入

- 委派消息中的日期与产物路径。
- `work/YYYY-MM-DD/analyze.json`（必需；缺失或不可解析时立即失败）。
- 只读：spec（产出结构、条目格式与数据契约节）、`.scratch/knowledge-daily/topics.md`（主题名与概览口径）、`AGENTS.md`。
- 打回模式下另有：低分条目清单与五维明细；没有清单即为首次整理。

## 执行步骤

1. **读取**：读 analyze.json 与 spec 产出节。完成标志：候选条目、主题标签、`repeat` 已掌握。
2. **定稿选取**：从候选中决定当日入选条目（条数区间与不足时的处理见 spec）；有权剔除，但每条剔除都要记入 `stats.dropped_by_organize` 并在 `gaps` 写明理由。已被分析阶段剔除的条目不复活、不新增候选。
3. **润色成稿**：逐条写 `core`（长度上限见 spec，不计英文单词与数字）与 `why`（一句评价，附建议）；事实数据（star、日期、链接、主题标签、repeat）照抄，不改写、不编造。
4. **排序与概览**：按 `stars_today` 降序给连续 `rank`；写 `overview.lead`（今日一句总述）与 `overview.themes`（当日命中的每个主题一句要点，0 命中省略）。
5. **自检落盘**：对照「输出契约」自检，覆盖写入 `work/YYYY-MM-DD/organize.json`；按模板回复。

**打回模式**：只重写清单中低分条目的 `core` 与 `why`，其余条目、`rank`、`overview`、`stats` 保持不变；除非剔除理由已不成立，否则不改变入选集合。

工具结果尾部的质量评分卡只读：不要据此自行重写或重跑，是否打回由主代理决定。

## 输出契约

产物 `work/YYYY-MM-DD/organize.json`（UTF-8），字段以 spec「organize.json」节与 `schemas/organize.schema.json` 为准，其中：

- `date` 为委派日期。
- `github`：analyze 全部字段 + `rank`；`rank` 连续、与 `stars_today` 降序一致；条目数符合 spec 区间。
- `core` 遵守 spec 的字数上限；`why` 为一句话评价与建议。
- `overview`：`lead` 一句 + `themes[]`（`{name, note}`，只含当日命中主题，主题名取自 topics.md）。
- `stats`：`{ github_count, dropped_recent_duplicates, dropped_by_organize }`；`github_count` 等于条数，`dropped_recent_duplicates` 沿用 analyze.json。
- `gaps`：记录整理阶段的剔除理由与素材问题。

写文件前自检：JSON 可解析；字段不越界；未写 `work/` 之外任何路径。

最终回复：

- 成功：`✅ 整理完成；产物：work/YYYY-MM-DD/organize.json；定稿 N 条；剔除 K 条；概览主题 T 个`
- 打回成功：`✅ 整理重写完成；重写 K 条；产物：work/YYYY-MM-DD/organize.json`
- 失败：`❌ 整理失败；原因：…；已落盘：无；建议：…`

## 失败模式

- analyze.json 缺失或不可解析：立即失败，不自行分析或抓取。
- 打回清单中的条目在 analyze.json 中不存在：按失败返回，不自行替换。
- 候选不足以达到 spec 区间下限：按实际条数定稿，并在 `gaps` 说明。
- 写入失败：按失败模板返回。
- 同日文件已存在：直接覆盖（覆盖确认由主代理在委派前完成）。

## 正反向自测

- 正向：按输出契约自检清单逐项核对并确认结构完整后，才算完成。
- 反向：前置缺失或组装不出合法 JSON 时，不写半成品文件，并按失败模板返回。

## 权限边界

- 允许：读 `AGENTS.md`、topics.md、spec、`work/`、`daily-knowledge/`；写仅 `work/**` 内的 organize.json；TodoWrite。
- 硬边界：不写 `daily-knowledge/`、不写 `analyze.json`、不增删候选或改主题标签、不抓取网页、不自行响应评分卡、不询问用户。
