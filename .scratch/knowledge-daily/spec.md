# 知识采集系统 · 需求规格

**Feature:** knowledge-daily
**Status:** ready-for-agent

## 问题陈述

每天要在 GitHub 上冒头的新项目很多：手动浏览耗时、容易漏掉重点；只看累计 star 分不清「今天真正在涨」的项目；看过的东西没有沉淀，重复出现的项目无法识别。需要一个每天手工触发一次、只依赖 GitHub、自动采集当日趋势、分析后产出中文知识日报并长期积累在仓库里的工作流。

## 方案

由 opencode 子代理驱动的一套零代码工作流：

- 用户说「开始今天的知识采集」，一次跑完 采集 → 分析 → 输出 三段。
- 采集：用 GitHub 搜索 API 拉候选集，逐个算出「今日新增 star」，按它降序取前 15–20 个项目。
- 分析：按 6 个关注主题给项目打标签、做 30 天时间去重，生成含评价的初稿。
- 输出：写入 `output/YYYY-MM-DD.md` 中文知识日报。
- 中间产物按天落在 `work/YYYY-MM-DD/`（本地保留，不进 git）。
- 三段各由 `.opencode/agent/` 下的一个子代理承担，流程细节由 `.agents/skills/` 下对应技能承载；主代理按「编排协议」串联；字段、权限与失败语义见「子代理设计」节。

## 用户故事

1. 作为用户，我希望用一句固定触发语启动当天采集，以便不用记忆复杂命令。
2. 作为用户，我希望一次触发自动跑完采集→分析→输出，以便中途无需人工介入。
3. 作为用户，我希望失败后说「继续知识采集」从断点续跑，以便不浪费已完成的阶段。
4. 作为用户，我希望同日重跑时先收到提示并三选一（重新采集并覆盖 / 仅重写日报 / 取消），以便按需刷新数据或只修补日报。
5. 作为用户，我希望日报按本地日期（UTC+8）归属，以便与我的一天对齐。
6. 作为读者，我希望采集只依赖 GitHub 一个数据源，以便口径单一、维护简单。
7. 作为读者，我希望用 GitHub 搜索 API（而非网页抓取）拉候选，以便零脚本、结果可追溯。
8. 作为读者，我希望候选口径为「近 1 日有推送、累计 star≥100」，以便覆盖真正活跃而非刚发布的仓库。
9. 作为读者，我希望按「今日新增 star」排序，以便看到当天真正在涨的项目。
10. 作为读者，我希望今日新增 star 优先用本地历史差分、无历史时用官方 star 历史接口兜底，以便在零额外成本与准确性之间取平衡。
11. 作为读者，我希望两次都拿不到星增量时如实记 null、不编造，以便数据可信。
12. 作为读者，我希望每轮额外 API 调用不超过约 20 次，以便未认证也能稳定跑完。
13. 作为分析者，我希望采集字段齐全（全名、描述、语言、总 star、今日新增 star、fork、链接），以便分析阶段不必回头补抓。
14. 作为维护者，我希望原始数据全量保留在 work/、不做删减，以便随时复查。
15. 作为读者，我希望 GitHub 趋势每日输出 15–20 个项目，以便篇幅稳定。
16. 作为读者，我希望每个项目带上关注主题标签，以便一眼看出它属于哪个板块。
17. 作为读者，我希望一个项目可命中多个主题，以便标签如实反映内容。
18. 作为读者，我希望不属于任何主题的项目标 `[其他]`，以便不遗漏高价值内容。
19. 作为读者，我希望 30 天内出现过的条目默认不再输出（有新进展除外），以便不重复看到旧内容。
20. 作为读者，我希望有新进展的条目才突破 30 天窗口、判断不了视为无进展，以便去重保守可靠。
21. 作为读者，我希望更早历史出现过的条目照常输出并标记「🔁 重复：上次 YYYY-MM-DD」，以便知道它再次出现。
22. 作为读者，我希望 30 天内突破的条目追加一句新进展，以便知道为什么值得再提。
23. 作为维护者，我希望历史查询直接读 output/ 下全部 md、不建索引，以便零维护。
24. 作为读者，我希望每天一个文件 `output/YYYY-MM-DD.md`，以便一天一档、便于归档。
25. 作为读者，我希望结构固定：日期标题 → 今日概览 → GitHub 趋势，以便阅读顺手。
26. 作为读者，我希望今日概览先给一句总述、再按主题分点，以便快速抓住当天重心、不再是一整段密集文字。
27. 作为读者，我希望概览里 0 命中的主题直接省略，以便篇幅干净。
28. 作为读者，我希望条目格式统一：标题 + 链接 + 核心内容 + 一句「为什么值得关注」，以便快速扫读。
29. 作为读者，我希望核心内容严格限制在 100 个汉字以内，以便每条都短小易读。
30. 作为分析者，我希望分析项目只读 README 的前 500 汉字或前 500 词、截断时才扩到 1000，以便控制上下文与抓取成本。
31. 作为分析者，我希望素材补抓总量不超过约 20 次/天，以便不触发限流。
32. 作为读者，我希望日报为中文、项目名/标题保留原文，以便阅读自然。
33. 作为维护者，我希望日报中的结论可追溯到 work/ 的原始 json，以便有疑问时核查。
34. 作为维护者，我希望 work/ 中间 json 本地保留且不进 git，以便仓库干净。
35. 作为维护者，我希望 output/ 本地保留、不进 git，.scratch/knowledge-daily/topics.md、AGENTS.md 进入 git，以便仓库干净、知识资产有版本。
36. 作为维护者，我希望主题与范围由我在 .scratch/knowledge-daily/topics.md 手工维护（含数据库排除 MySQL/Oracle 系），以便随时调整关注面。
37. 作为维护者，我希望系统零代码（不写抓取与处理脚本）、采集靠子代理的 web 工具、配置用 md，以便维护成本最低。
38. 作为维护者，我希望 opencode 自身的 agent 配置不算「代码」，以便子代理设计不被零代码约束误伤。
39. 作为维护者，我希望三个子代理各自有明确的角色职责、输入、输出、权限、失败模式、禁止行为与质量自查，以便行为可预期、出错可诊断。
40. 作为维护者，我希望子代理按最小权限运行（只开必要的读写路径与网络访问，禁用 bash 等），以便自动化流程不会误伤仓库或系统。
41. 作为维护者，我希望段间以固定的 JSON 数据契约传递（collect.json / analyze.json），以便段间不漂移、产出可追溯。
42. 作为维护者，我希望子代理失败时返回统一格式的错误摘要、不落半成品，以便主代理能决定续跑或终止。
43. 作为维护者，我希望条目文字由分析段生成初稿、输出段组装润色，以便抓取集中在前两段、输出段保持纯写作。
44. 作为维护者，我希望「继续知识采集」按 work/ 已有产物断点续跑、删除对应产物即可强制重跑某阶段，以便恢复与调试都可控。
45. 作为用户，我希望「仅重写日报」时 work 当天数据保持不变，以便原始数据始终可追溯。
46. 作为维护者，我希望三个子代理的流程细节由各自技能承载、agent 只保留「何时委派 + 加载技能」，以便流程只有一份来源。
47. 作为维护者，我希望每个技能写清使用场景、输入、执行步骤、输出契约、失败模式、正反向自测与权限边界，以便执行行为可预期、出错可诊断。
48. 作为维护者，我希望技能 frontmatter 至少包含 `name`、`description`、`allowed-tools`，且 `allowed-tools` 按最小权限只列必要工具并收敛路径/域名，以便能力边界清晰。
49. 作为维护者，我希望每个子代理只能加载本阶段技能、主代理不能自行加载流程技能，以便技能加载同样受最小权限约束。
50. 作为读者，我希望分析段为每条内容给出「评价 + 理由 + 建议」，以便知道为什么值得关注、依据是什么、是否值得跟进或怎么用。

## 实现决策

- 系统形态：子代理三段（采集 / 分析 / 输出）各加载对应技能执行，段间以 json 传递中间产物，按天落在 `work/YYYY-MM-DD/`。
- 技能机制：流程细节由 `.agents/skills/` 下三个技能承载（opencode 与 agent 兼容运行时均扫描），agent 只保留触发、模型与权限壳；`allowed-tools` 供兼容运行时声明，opencode 会忽略，实际最小权限由 agent permission 与 `opencode.json` 顶层 deny 执行。
- 评价写作：分析段每条初稿含「评价 + 理由 + 建议」——评价即 `why`、理由落 `core`、建议并入 `why`；不新增数据契约字段。
- 触发：固定触发语「开始今天的知识采集」；续跑语「继续知识采集」。
- 同日重跑：当天 output 已存在时先提示，三选一（重新采集并覆盖 / 仅重写日报 / 取消），默认重新采集并覆盖；「仅重写」时保留 work 当日数据。
- 日期归属：本地日期（UTC+8）。
- 采集源：仅 GitHub；不使用 Hacker News，也不做多源去重。
- GitHub 候选集：调用搜索 API `GET https://api.github.com/search/repositories?q=pushed:>=<T-1d>+stars:>=100&sort=stars&order=desc&per_page=100`，`{T-1d}` 为委派日期减 1 天，取首页前 100。不再按语言分榜，因此不产出 `boards`/`board_ranks`。
- 今日新增 star：为候选逐个赋值，口径统一为**当日新增**。基线取 `work/**/collect.json` 中**日期早于今日的最近一次**该 repo 的 `stars_total`；仅当该基线恰为**上一自然日**时才用于差分（同日重跑因此不会读到当日自身产物）。优先级为 ① 本地差分——`stars_today = 当前 stars_total − 基线`，`stars_today_source=local_diff`；② 官方兜底——无上一自然日基线时调 `GET https://api.github.com/repos/{owner}/{repo}/stargazers/history`，取当日（或最近一日）增量，`stars_today_source=star_history`，按 `stars_total` 降序依次兜底，调用总量 ≤20 次/轮；③ 都不可得记 `stars_today=null`。
- 未认证限流：采集段以未认证请求运行（`webfetch` 无法携带 token）——搜索端点约 10 次/分、核心端点约 60 次/时；star_history 调用上限 20 次即为稳定运行而设。
- 排序与选取：丢弃 `stars_today=null` 的候选，其余按 `stars_today` 降序取前 15–20；不足 15 按实际数量输出。
- 主题定义：6 个关注主题见 `.scratch/knowledge-daily/topics.md`；数据库主题排除 MySQL/MariaDB/Percona/Oracle；一个项目可同时命中多个主题。
- 时间去重（仅 GitHub）：30 天内出现过的 repo 默认不输出，有新进展才输出并标记；更早历史出现过的照常输出并标记。标记格式 `🔁 重复：上次 YYYY-MM-DD`，30 天内突破的追加一句新进展。新进展判定方式为核查 release / star 变化 / 重大新闻，判断不了视为无进展。
- 历史查询：直接读 `output/` 下全部 md，不建索引文件。
- 产出：单文件 `output/YYYY-MM-DD.md`，中文；结构为日期标题、今日概览、GitHub 趋势（按今日新增 star 降序、条目带主题标签）。不再有独立主题节。
- 概览：先一句总述，再按主题分点（每主题一句要点，0 命中省略）。
- 条目文字：核心内容 ≤100 个汉字（不含「为什么值得关注」，不计英文单词与数字）；「为什么值得关注」独立一句，保留分析段的评价与建议。
- README 限读：分析段仅在仓库描述过短或不明时读 README，且只读前 500 汉字（中文）或前 500 词（英文）；若该处句子/段落被截断则扩到 1000；素材补抓总量 ≤20 次/天。
- 数据与版本控制：`work/`、`output/` 加入 `.gitignore`；除 `work/`、`output/` 外的仓库文件均纳入版本控制。
- 规范来源：本 spec 是工作流细则的单一来源；`AGENTS.md` 只保留入口级约束与指向本 spec、`.scratch/knowledge-daily/topics.md` 的指针。

## 子代理设计

三个子代理定义在 `.opencode/agent/`，均为 `mode: subagent`、`hidden: false`——可被主代理自动委派，也可 `@` 手动单跑调试。流程细节不写在 agent 里，而由 `.agents/skills/` 下的三个技能承载（opencode 与 agent 兼容运行时均扫描该路径）：

| 技能 | 阶段 | 对应子代理 |
| --- | --- | --- |
| `knowledge-collect` | 采集 | `knowledge-collect` |
| `knowledge-analyze` | 分析 | `knowledge-analyze` |
| `knowledge-write` | 输出 | `knowledge-write` |

### 命名与模型

| 子代理 | 阶段 | 模型 | 温度 |
| --- | --- | --- | --- |
| `knowledge-collect` | 采集 | `oc-go/deepseek-v4.1-flash` | 0 |
| `knowledge-analyze` | 分析 | `oc-go/deepseek-v4.1-flash` | 0.1 |
| `knowledge-write` | 输出 | `oc-go/deepseek-v4.1-flash` | 0.4 |

不指定模型时会继承主代理；当前统一指定 `oc-go/deepseek-v4.1-flash`。

### agent 与技能的分工

- agent frontmatter：`name`、`description`（写清何时委派）、`mode`、`model`、`temperature`、`permission`、`hidden`。
- agent 正文是壳：一句话角色 + 「先用 skill 工具加载对应技能，再严格按技能执行」；技能加载失败时按失败模板返回。
- 技能 frontmatter：`name`、`description`（写清何时加载）、`allowed-tools`（按最小权限列必要工具并对路径/域名收敛；opencode 忽略该字段，实际限制由 agent `permission` 执行）。
- 技能正文必须包含：使用场景、输入、执行步骤、输出契约、失败模式、正反向自测（各一句）与权限边界。
- 技能承载执行细节；数据契约仍以本 spec 为单一来源；agent 与技能的写作规范（含不复述本 spec 已定义的口径）见 `docs/agents/CODING_STANDARDS.md`。

### 权限（最小权限）

- 用 `permission` 字段表达（`tools` 字段已废弃）；每个子代理以 `"*": deny` 兜底，再显式白名单。
- 权限路径 pattern 相对于 worktree 根目录（如 `work/**`、`output/**`；Windows 下大小写不敏感），因此无需绝对路径。
- 技能加载按 agent 收口：每个子代理的 `skill` 只放行本阶段技能（`"*": deny` + 本技能 `allow`）；`opencode.json` 顶层 `permission.skill` 对 `knowledge-*` deny，主代理不能自行加载流程技能。
- 能力矩阵：
  - 采集：读 spec/topics/AGENTS.md 与 `work/`（含历史 collect.json 供差分）；写 `work/**`；glob、webfetch、todowrite 允许；skill 仅允许 `knowledge-collect`；bash/task/question/websearch 禁止。
  - 分析：在采集基础上增加读 `output/**` 与 glob、grep（供历史去重）；写仍仅限 `work/**`；skill 仅允许 `knowledge-analyze`。
  - 输出：读 spec/AGENTS.md、`work/**`、`output/**`；写仅限 `output/**`；skill 仅允许 `knowledge-write`；不抓取网页。
- 全部子代理禁止访问项目外目录，禁止向用户提问。

### 内容分工

- 分析段生成每条条目的 core（≤100 个汉字，承载理由与支撑事实）与 why（1 句评价，附是否跟进/怎么用的建议）初稿；输出段只做组装、润色、概览与总述。
- 素材补足：GitHub 条目优先凭描述概括，描述过短或不明时才抓 README，且只读前 500 汉字/前 500 词、截断才扩到 1000；补抓软上限约 20 次/天。

### 失败语义

- 完成标志：正式 JSON 完整写出；失败时不落正式文件，已抓数据可写 `<阶段>.partial.json` 仅供人工诊断（主代理与续跑忽略）。
- 单源失败：搜索 API 失败即采集阶段失败；star_history 单次失败记 `gaps` 并把该条 `stars_today` 记 null；前置产物缺失或不可解析，均判阶段失败。
- 新进展核查失败：保守视为无进展（不计入失败）。
- 同日覆盖确认由主代理在委派输出段前完成；输出子代理直接覆盖写入。

## 数据契约

中间产物按天落在 `work/YYYY-MM-DD/`，段间以此传递；JSON 为 UTF-8，`collected_at` 为本地时间（UTC+8，格式 `YYYY-MM-DD HH:mm`，不带时区）。

### collect.json（采集产物）

```jsonc
{
  "date": "YYYY-MM-DD",
  "collected_at": "YYYY-MM-DD HH:mm",
  "github": [
    {
      "full_name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "description": "仓库原文描述 | null",
      "language": "Go | null",
      "stars_total": 12345,
      "stars_today": 120,
      "stars_today_source": "local_diff | star_history | null",
      "forks": 1234,
      "created_at": "YYYY-MM-DD",
      "pushed_at": "YYYY-MM-DD"
    }
  ],
  "gaps": ["如实记录抓取异常、字段缺失，以及未纳入的候选数量与 star_history 调用次数"]
}
```

### analyze.json（分析产物）

```jsonc
{
  "date": "YYYY-MM-DD",
  "github": [
    {
      "...collect.github 全部字段...",
      "themes": ["AI / LLM", "云原生"],
      "rank": 1,
      "repeat": null,
      "core": "≤100 个汉字的核心内容初稿",
      "why": "一句为什么值得关注初稿"
    }
  ],
  "overview": {
    "lead": "今日一句总述",
    "themes": [
      { "name": "AI / LLM", "note": "该主题当日要点一句" }
    ]
  },
  "stats": { "github_count": 18, "dropped_recent_duplicates": 4 },
  "gaps": []
}
```

### 约定

- `repeat`：仅历史出现过才有，形如 `{ "last_seen": "YYYY-MM-DD", "new_progress": "一句新进展 | null" }`；`last_seen` 必须真实存在于 `output/` 历史。
- GitHub 15–20 条按 `stars_today` 降序；`themes` 为空数组时在日报中渲染为 `[其他]`。
- 30 天窗口内的历史条目须有新进展才保留（无法判定视为无进展，剔除并计入 `stats.dropped_recent_duplicates`）；30 天外的照常输出并标 `repeat`。
- `overview.themes` 只含当日命中的主题（0 命中省略），`note` 为该主题要点。
- `work/` 原始数据全量保留、不做删减，并本地留存不进 git。

## 编排协议

三段由主代理（默认 build）编排；三个子代理各自只执行本阶段。子代理定义见 `.opencode/agent/`。

### 委派

- 用 Task 工具依次委派 `knowledge-collect` → `knowledge-analyze` → `knowledge-write`，上一段完成后才委派下一段。
- 委派消息模板：`阶段：<采集|分析|输出>；日期：YYYY-MM-DD；产物：<work/YYYY-MM-DD/collect.json | work/YYYY-MM-DD/analyze.json | output/YYYY-MM-DD.md>。先加载技能 <knowledge-collect|knowledge-analyze|knowledge-write>，再按其「输入」与「执行步骤」执行；数据契约见 .scratch/knowledge-daily/spec.md。`
- 完成判定：产物文件存在（collect.json / analyze.json / output 日报），不深度校验内容。
- 三次委派的结果（成功/失败摘要）汇总后一并报告给用户。

### 断点续跑（「继续知识采集」）

| 现状 | 动作 |
| --- | --- |
| 无 collect.json | 从采集开始 |
| 有 collect.json、无 analyze.json | 从分析开始 |
| 有 analyze.json、无当日 output | 从输出开始 |
| 当日 output 已存在 | 已完成；除非用户选择重跑，否则不动作 |

不重跑已完成阶段。

### 同日重跑（当日 output 已存在）

主代理提示并让用户三选一，默认第一项：

1. **重新采集并覆盖**：重跑采集 → 分析 → 输出（当日 work 数据被新数据覆盖）。
2. **仅重写日报**：保留 work 当日数据，只重跑输出阶段。
3. **取消**：什么都不做。

### 失败处理与恢复

- 子代理失败：主代理向用户报告原因与建议后停止；用户说「继续知识采集」时按断点续跑。
- 单阶段手动触发（`@knowledge-collect` 等）允许用于调试；前置产物缺失时该阶段应以前置缺失失败，而非自动重跑前段。
- 强制重跑某阶段：删除 `work/YYYY-MM-DD/` 下对应产物文件（或 `output/` 当日文件）后重新触发。

## 验收决策

- 本项目不含代码、无自动化测试；验收只看产出文件的外部可观察行为，不关心子代理内部实现。
- 每次产出后可抽查的验收点：
  - 结构完整：日期标题、今日概览（一句总述 + 主题分点）、GitHub 趋势齐全；条目格式符合条目格式约定。
  - 数量正确：GitHub 趋势 15–20 条。
  - 排序正确：按 `stars_today` 降序；`stars_today` 为 null 的候选未进入列表。
  - 主题边界：数据库主题打标签时排除 MySQL/MariaDB/Percona/Oracle 系；不属于任何主题的项目标 `[其他]`。
  - 篇幅：每条核心内容 ≤100 个汉字。
  - 去重可核查：每个 🔁 标记中的日期在 output/ 历史中确实存在；30 天内无新进展的旧条目未出现。
  - 可追溯：work/YYYY-MM-DD/ 的 json 覆盖当天全部产出条目。
- 子代理与技能可观察性：`opencode agent list` 可见三个 subagent，且各自 `skill` 只放行本阶段技能、主代理侧 `knowledge-*` 为 deny；`opencode debug skill` 可列出三份技能；SKILL.md frontmatter 含 `name`/`description`/`allowed-tools`（无 Bash/Task/WebSearch/Skill；webfetch 域名按技能各自收敛：采集→api.github.com、分析→github.com、输出不抓取）、正文含七节与权限边界。
- 失败行为：前置产物缺失时，委派对应子代理应以「前置缺失」失败且不产出正式文件；失败摘要符合约定模板。
- 同日重跑：当日 output 已存在时出现三选一提示；选「仅重写日报」后 work/ 当日文件保持不变。
- 首次端到端验收：手工触发一次完整流程，按上述清单人工检查。
- 无既有测试可作先例（新项目、零代码）。

## 范围外

- 自动调度：系统只支持手工触发，不做定时运行。
- 任何抓取/处理代码或脚本。
- 通知与发布渠道（邮件、IM、博客等）。
- 采集源扩展：当前仅 GitHub，不接 Hacker News 或其他站点。
- issue tracker 的完整配置（triage labels、domain docs）：本次只落地最小 tracker 配置。

## 备注

- `.scratch/knowledge-daily/topics.md` 的主题与范围关键词由用户随时手工增删。
- 本 spec 落在 local markdown tracker：`.scratch/knowledge-daily/spec.md`；tracker 配置见 `docs/agents/issue-tracker.md`。
- 本 spec、`docs/agents/`、`.opencode/agent/`、`.agents/skills/` 与 `opencode.json` 建议一并纳入 git 提交范围（待用户确认）。
