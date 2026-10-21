# 知识采集系统 · 需求规格

**Feature:** knowledge-daily
**Status:** ready-for-agent
**Updated:** 2026-10-22（v3：自由标签、日报展示、daily-knowledge、token md、GitHub Actions 定时运行）

## 问题陈述

每天要在 GitHub 上冒头的新项目很多：手动浏览耗时、容易漏掉重点；只看累计 star 分不清「今天真正在涨」的项目；看过的东西没有沉淀，重复出现的项目无法识别。固定的 6 个关注主题又把学习面限制住了。整条链路若全靠子代理交互式完成，抓取成本高、口径不可复现、产物质量也无人审计。

需要一个能每天自动发布的工作流：采集由脚本确定性完成以省成本，分析与整理交给子代理以保证判断与文笔，产出中文知识日报并长期积累；同时用 schema 校验、确定性质量评分与 token 统计，让产物的「对不对」「好不好」「花了多少」都可见。日报要能展示单条评分与项目总 star，成本要有一份人可读的 markdown，产物要能每天提交到公开仓库。

## 方案

- 用户说「开始今天的知识采集」，一次跑完 **采集 → 分析 → 整理 → 渲染** 四段，并汇报 token 成本。本地与 GitHub Actions 共用同一套步骤。
- **采集（Python 脚本，必须使用采集凭证）**：用 GitHub 搜索 API 拉候选集，逐个算出「今日新增 star」，按它降序取前 15–20，写 `collect.json`。
- **分析（子代理）**：只做内容分析——自由打标签（不再受固定主题表约束）、30 天时间去重、核查新进展、写分析要点与评价，写 `analyze.json`。
- **整理（子代理）**：职责分离后的定稿者——从分析结果中决定当日入选条目、润色为成稿、定排序与概览，写 `organize.json`。
- **渲染（主代理）**：按固定模板把 `organize.json` 机械填充为 `daily-knowledge/YYYY-MM-DD.md`，不改写文字；每条附总 star、今日新增 star 与质量评分。
- **质量与成本**：`schemas/` 是字段唯一来源，`scripts/validate.py` 做契约校验；`.opencode/plugins/` 的 hook 在整理产物落盘后调 `scripts/score.py` 做 5 维打分并写 `score.json`，低于 60 分打回重来；token 插件聚合消耗，同时写 `daily-knowledge/tokens/YYYY-MM-DD.md` 供人阅读。
- **自动发布（GitHub Actions）**：每天 00:00 UTC（08:00 UTC+8）无头运行同一套流水线，把日报、token 报告与每日 `collect.json` 提交回公开仓库 `zoayoung/daily-collector` 的 `main` 分支。
- 中间产物按天落在 `work/YYYY-MM-DD/`（仅每日 `collect.json` 进 git，其余本地保留）。

## 用户故事

1. 作为用户，我希望用一句固定触发语启动当天采集，以便不用记忆复杂命令。
2. 作为用户，我希望一次触发自动跑完采集→分析→整理→渲染，以便中途无需人工介入。
3. 作为用户，我希望失败后说「继续知识采集」从断点续跑，以便不浪费已完成的阶段。
4. 作为用户，我希望同日重跑时先收到提示并三选一（重新采集并覆盖 / 仅重写日报 / 取消），以便按需刷新数据或只修补日报。
5. 作为用户，我希望日报按本地日期（UTC+8）归属，以便与我的一天对齐。
6. 作为读者，我希望采集只依赖 GitHub 一个数据源，以便口径单一、维护简单。
7. 作为维护者，我希望采集由 Python 脚本完成而不是子代理交互抓取，以便口径可复现、token 成本可预期。
8. 作为维护者，我希望采集脚本必须携带 `GITHUB_TOKEN` 认证运行，以便配额稳定、口径可预期。
9. 作为读者，我希望用 GitHub 搜索 API 拉候选，口径为「近 1 日有推送、累计 star≥100」，以便覆盖真正活跃而非刚发布的仓库。
10. 作为读者，我希望按「今日新增 star」排序，以便看到当天真正在涨的项目。
11. 作为读者，我希望今日新增 star 优先用本地历史差分、无历史时用官方 star 历史接口兜底，以便在零额外成本与准确性之间取平衡。
12. 作为读者，我希望两次都拿不到星增量时如实记 null、不编造，以便数据可信。
13. 作为读者，我希望每轮 star 历史兜底调用不超过约 20 次，以便控制抓取耗时与配额消耗。
14. 作为分析者，我希望采集字段齐全（全名、描述、语言、总 star、今日新增 star、fork、链接），以便后续阶段不必回头补抓。
15. 作为维护者，我希望原始数据全量保留在 work/、不做删减，以便随时复查。
16. 作为读者，我希望日报每日输出 15–20 个项目，以便篇幅稳定。
17. 作为读者，我希望每个项目带上自由标签，以便一眼看出它涉及哪些技术方向。
18. 作为读者，我希望一个项目可命中多个标签，以便标签如实反映内容。
19. 作为读者，我希望未打标签的项目标 `[其他]`，以便不遗漏高价值内容。
20. 作为读者，我希望 30 天内出现过的条目默认不再输出（有新进展除外），以便不重复看到旧内容。
21. 作为读者，我希望有新进展的条目才突破 30 天窗口、判断不了视为无进展，以便去重保守可靠。
22. 作为读者，我希望更早历史出现过的条目照常输出并标记「🔁 重复：上次 YYYY-MM-DD」，以便知道它再次出现。
23. 作为读者，我希望 30 天内突破的条目追加一句新进展，以便知道为什么值得再提。
24. 作为分析者，我希望分析阶段只负责内容判断（标签、去重、评价），不决定入选条数与排版，以便职责单一。
25. 作为整理者，我希望在分析结果之上决定当日入选条目数与排序，以便按当天节奏控制篇幅。
26. 作为维护者，我希望整理阶段的每次剔除都记数与说明理由，以便事后追查。
27. 作为读者，我希望核心内容严格限制在 100 个汉字以内，以便每条都短小易读。
28. 作为读者，我希望整理阶段产出成稿文字与概览，以便渲染阶段只做排版。
29. 作为读者，我希望今日概览先给一句总述、再按标签分组，以便快速抓住当天重心。
30. 作为读者，我希望概览里 0 命中的分组直接省略，以便篇幅干净。
31. 作为读者，我希望日报由主代理按固定模板机械渲染、不改写文字，以便每次输出稳定可复现。
32. 作为读者，我希望结构固定：日期标题 → 质量评分 → 今日概览 → GitHub 趋势，以便阅读顺手。
33. 作为读者，我希望条目格式统一：标题 + 标签 + Star/评分 + 链接 + 核心内容 + 一句「为什么值得关注」，以便快速扫读。
34. 作为读者，我希望日报为中文、项目名/标题保留原文，以便阅读自然。
35. 作为维护者，我希望 JSON 字段以 `schemas/` 为唯一来源，以便契约不漂移。
36. 作为维护者，我希望有校验脚本同时检查采集脚本与两个子代理的产物是否符合设计，以便字段问题在进入下一步前暴露。
37. 作为维护者，我希望校验失败时把错误清单回传给子代理重跑，以便自动修复而不是人工猜。
38. 作为维护者，我希望同一阶段连续 3 次校验失败就终止任务，以便不无限重试。
39. 作为维护者，我希望整理子代理每次写入或编辑 `organize.json` 后自动触发质量评分 hook，以便内容问题立刻可见。
40. 作为维护者，我希望评分由 5 个固定维度构成（摘要质量 25、技术深度 25、格式规范 20、标签精度 15、空洞词检测 15），以便尺度统一。
41. 作为读者，我希望评分输出可视化进度条、每维得分与 A/B/C 等级，以便一眼看出短板。
42. 作为维护者，我希望等级规则固定为 A≥80、B≥60、C<60，以便跨天可比。
43. 作为维护者，我希望单条项目低于 60 分时打回重新分析并重新定稿，以便不让低质条目进日报。
44. 作为维护者，我希望同一条目连续 3 次仍低于 60 分就终止任务且不产出日报，以便问题不被掩盖。
45. 作为用户，我希望主代理在收尾时给出本次 token 总消耗，以便知道这天的采集成本。
46. 作为用户，我希望 token 统计细分到每个子代理与主代理，以便定位成本大头。
47. 作为维护者，我希望 token 统计按轮追加、不被同日覆盖清零，以便成本是事实、可回溯。
48. 作为维护者，我希望关注面不再由固定主题表限制，以便我按兴趣全面学习。
49. 作为维护者，我希望采集、校验、评分用 Python，其余阶段零脚本，以便成本与可维护性兼顾。
50. 作为维护者，我希望 opencode 自身的 agent 配置与插件不算「脚本产物」，以便设计不被约束误伤。
51. 作为维护者，我希望两个子代理各自有明确的角色职责、输入、输出、权限、失败模式与质量自查，以便行为可预期、出错可诊断。
52. 作为维护者，我希望子代理按最小权限运行（只开必要的读写路径与网络访问，禁用 bash 等），以便自动化流程不会误伤仓库或系统。
53. 作为维护者，我希望段间以固定的 JSON 数据契约传递（collect.json / analyze.json / organize.json），以便段间不漂移、产出可追溯。
54. 作为维护者，我希望子代理失败时返回统一格式的错误摘要、不落半成品，以便主代理能决定续跑或终止。
55. 作为维护者，我希望「继续知识采集」按 work/ 已有产物断点续跑、删除对应产物即可强制重跑某阶段，以便恢复与调试都可控。
56. 作为用户，我希望「仅重写日报」时 work 当天数据保持不变，以便原始数据始终可追溯。
57. 作为维护者，我希望两个子代理的流程细节由各自技能承载、agent 只保留「何时委派 + 加载技能」，以便流程只有一份来源。
58. 作为维护者，我希望技能 frontmatter 至少包含 `name`、`description`、`allowed-tools`，且 `allowed-tools` 按最小权限只列必要工具并收敛路径/域名，以便能力边界清晰。
59. 作为维护者，我希望每个子代理只能加载本阶段技能、主代理不能自行加载流程技能，以便技能加载同样受最小权限约束。
60. 作为读者，我希望分析阶段为每条内容给出「评价 + 理由 + 建议」，以便知道为什么值得关注、依据是什么、是否值得跟进或怎么用。
61. 作为读者，我希望项目改用自由标签而不是固定主题，以便覆盖我尚未预设的学习方向。
62. 作为读者，我希望每个项目带 2–4 个标签，以便一眼看出它的技术角度。
63. 作为读者，我希望标签由分析阶段按内容生成，以便标签如实反映项目而不是被白名单裁剪。
64. 作为读者，我希望概览把零散标签合并成不超过 6 组，以便标签变多后日报仍然易读。
65. 作为维护者，我希望删除固定主题表，以便系统不再静默缩小采集与展示范围。
66. 作为读者，我希望每条项目显示总 star 与今日新增 star，以便同时判断体量与当天热度。
67. 作为读者，我希望每条项目显示质量评分与 A/B/C 等级，以便知道系统为什么认为它写得好或不好。
68. 作为读者，我希望标题下保留均分与等级分布，以便一眼看到当天整体质量。
69. 作为读者，我希望评分不可用时省略评分部分而不是编造数字，以便数据始终可信。
70. 作为读者，我希望 star 数字带千分位，以便大数字快速可读。
71. 作为读者，我希望日报存放在 `daily-knowledge/` 而不是 `output/`，以便目录名直接说明内容。
72. 作为维护者，我希望现有历史日报迁移到新目录，以便改名后去重与重复标记仍然准确。
73. 作为维护者，我希望路径常量、校验、测试与文档一起改名，以便仓库里只有一套路径口径。
74. 作为读者，我希望 token 报告以 markdown 存在 `daily-knowledge/tokens/YYYY-MM-DD.md`，以便直接阅读。
75. 作为读者，我希望 token 报告按 run 与代理拆分并给出当日合计，以便定位成本大头。
76. 作为维护者，我希望 token 报告在每次运行后自动生成，以便不靠手工整理。
77. 作为维护者，我希望 token 报告随日报一起提交，以便成本历史与产出放在同一处。
78. 作为维护者，我希望流水线每天 08:00（UTC+8）由 GitHub Actions 自动运行，以便不需要每天手工触发。
79. 作为维护者，我希望同一套流水线仍能在本地手动触发，以便调试与补跑。
80. 作为维护者，我希望 CI 复用采集、分析、整理、渲染四段，以便线上与本地行为不分叉。
81. 作为维护者，我希望 CI 在当日日报已存在时跳过，以便定时任务幂等。
82. 作为维护者，我希望手动触发时可以强制覆盖当天，以便刷新数据或修补日报。
83. 作为维护者，我希望 CI 先跑单元测试再调用模型，以便契约问题不消耗 token。
84. 作为维护者，我希望 CI 失败时上传 `work/` 产物，以便下载现场排查。
85. 作为维护者，我希望 CI 失败后不自动重试，以便不重复烧钱。
86. 作为维护者，我希望 CI 把 `daily-knowledge/` 与每日 `collect.json` 提交回仓库，以便历史、去重与 star 差分持续可用。
87. 作为维护者，我希望除每日 `collect.json` 外的 `work/` 不进入 git，以便仓库不随天数膨胀。
88. 作为维护者，我希望模型密钥只存在于仓库 Secret，以便公开仓库不泄露凭证。
89. 作为维护者，我希望 CI 锁定 opencode 版本与模型，以便每天运行可复现。
90. 作为读者，我希望公开仓库每天出现一份新日报，以便不装本地工具也能阅读。
91. 作为维护者，我希望首次推送包含迁移后的历史日报，以便去重与趋势从第一天就完整。
92. 作为维护者，我希望默认分支为 `main`，以便与新仓库一致。
93. 作为维护者，我希望 CI 失败时最后一份已发布日报保持不变，以便发布质量不会被半成品污染。
94. 作为维护者，我希望 CI 只额外配置一个模型密钥，以便采集与回写都复用自带令牌。
95. 作为维护者，我希望 CI 在无头环境不向用户提问，以便定时任务不会卡住。
96. 作为维护者，我希望标签校验不再依赖固定词表，以便新增标签无需改配置。
97. 作为维护者，我希望 CI 先在临时分支上真实跑通再合并 `main`，以便推送后定时任务第一次就能成功。
98. 作为维护者，我希望 CI 冒烟同时覆盖「当日已存在则跳过」与 `force` 覆盖两条路径，以便幂等行为经过验证。

## 实现决策

- 系统形态：**采集脚本 + 分析子代理 + 整理子代理 + 主代理渲染**，由 GitHub Actions 定时运行。段间以 JSON 传递中间产物，按天落在 `work/YYYY-MM-DD/`。
- 本节之后的三节——子代理设计、数据契约、编排协议——同属实现决策的细则。
- 触发：本地固定触发语「开始今天的知识采集」；续跑语「继续知识采集」。CI 直接以同一触发语无头运行，不经过对话。
- 关注面（v3）：删除 `.scratch/knowledge-daily/topics.md`；分析阶段自由打标签，不再有固定主题白名单；`themes` 为空数组表示「未打标签」，日报渲染为 `[其他]`。
- 标签口径：每条建议 2–4 个标签；评分「标签精度」改为按标签个数给分（2–4 个满分、1 个中档、≥5 个降档、0 个 0 分），不再检查关键词证据。
- 概览口径：整理阶段把自由标签合并为不超过 6 组，再写 `overview.themes`；0 命中省略。
- 日报展示：每条元信息行固定为「Star：总数（今日 +增量）· 评分：总分 / 等级」；评分来自当日 `score.json`，按 `rank` 与 `full_name` 对齐；缺失时省略评分部分、其余照常。标题下保留「质量评分：均分 X · A a / B b / C c」。
- 产物目录（v3）：`output/` 重命名为 `daily-knowledge/`，文件名仍为 `YYYY-MM-DD.md`；现有历史日报迁入，作为去重依据。`KNOWLEDGE_OUTPUT_DIR` 默认值、校验脚本、测试与文档同步改名。
- token 报告：`.opencode/plugins/token-stats.js` 在刷新 `work/YYYY-MM-DD/tokens.json` 后，同时写 `daily-knowledge/tokens/YYYY-MM-DD.md`；内容按 run、按代理列出与 `tokens.json` 相同的字段，并给出当日合计。
- 自动运行（v3）：GitHub Actions 每日 00:00 UTC（08:00 UTC+8）触发；`ubuntu-latest`；步骤为检出 → 安装 uv 与 Node → 同步依赖 → 跑单元测试 → 安装锁定版本的 opencode → 无头执行 `opencode run --auto "开始今天的知识采集"` → 校验产物 → 提交回写。
- CI 参数：opencode 以 `@opencode/cli@2.0.26` 安装（`opencode-ai` 是 1.x 包，勿混用），所有代理统一使用 `oc-go/deepseek-v4.1-flash`；仓库内 `opencode.json` 固定 provider `oc-go` 与默认模型，`apiKey` 用 `{env:OC_GO_API_KEY}` 占位。
- CI 凭证：模型密钥只放在仓库 Secret `OC_GO_API_KEY`；采集与回写共用 Actions 自带的 `GITHUB_TOKEN`（`permissions.contents: write`），不额外配置 Personal Access Token。
- CI 幂等：启动 opencode 前检查当日 `daily-knowledge/<日期>.md`；存在且 `force=false` 则跳过并退出 0，`force=true` 按「重新采集并覆盖」执行。
- CI 失败：不自动重试；把 `work/<日期>/` 上传为 artifact，不提交半成品，最后一份已发布日报保持原样。
- CI 并发：同一 workflow 使用单一并发组，避免定时与手动触发重叠。
- CI 冒烟（交付门槛）：先在临时分支 `ci-smoke` 推送并 `workflow_dispatch` 真实跑通，覆盖 `force=true` 全流程与 `force=false` 跳过两种情形，再合并 `main`；不以 `act` 或本地 runner 代替真实 Actions。
- 首次发布：目标仓库 `https://github.com/zoayoung/daily-collector`（public），默认分支 `main`；本地用 `~/.ssh/git` 推送；首次提交包含迁移后的历史日报与现有测试。
- 采集脚本：`scripts/collect.py`，由主代理用 `uv run python scripts/collect.py --date YYYY-MM-DD` 执行；`--dry-run` 打印 JSON 不落盘。脚本承担抓取、今日新增 star、排序选取、`gaps` 全流程，产物与旧契约完全一致。
- 采集异常：未配置 `GITHUB_TOKEN`、搜索 API 失败、候选为空即脚本失败（退出码非 0、不写正式文件）；`star_history` 单次失败记 `gaps` 并把该条记 null。
- 今日新增 star 口径（沿用）：基线取 `work/**/collect.json` 中**日期早于今日的最近一次**该 repo 的 `stars_total`；仅当基线恰为**上一自然日**时才用于差分（同日重跑不会读到自身产物）。优先级：① 本地差分 `stars_today_source=local_diff`；② 官方兜底 `GET /repos/{owner}/{repo}/stargazers/history`，按 `stars_total` 降序依次兜底，总量 ≤20 次/轮，`stars_today_source=star_history`；③ 都不可得记 null。
- 排序与选取（沿用）：丢弃 `stars_today=null` 的候选，其余按 `stars_today` 降序取前 15–20；不足 15 按实际数量输出。
- 认证（必填，相对原始需求的扩展）：脚本从进程环境或项目根 `.env` 读取 `GITHUB_TOKEN`（兼容 `GH_TOKEN`），进程环境优先；缺失即失败，不退回未认证。`.env` 由脚本自行加载（opencode 不自动注入），`.env` 已被 git 忽略，模板见 `.env.example`。认证后配额：搜索 30 次/分、核心 5000 次/时。
- 分析阶段：只做自由标签、30 天时间去重、新进展核查、`core`/`why` 分析要点。**不决定入选条数、不写 `rank`/`overview`**。`core`/`why` 为分析要点，不设 100 汉字硬限。
- 整理阶段：从 analyze 候选中**定稿 15–20 条**（不足按实际），有权剔除但必须计入 `stats.dropped_by_organize` 并在 `gaps` 说明理由；负责 `rank`（按 `stars_today` 降序连续编号）、`overview`（自由标签合并 ≤6 组）、`core` ≤100 汉字（不计英文单词与数字）、`why` 一句评价与建议。
- 渲染：主代理按固定模板机械填充 `organize.json`，文字与数字照抄、不改写；模板见「编排协议 · 渲染模板」。标题下放质量评分摘要，每条放 star 与评分。
- 校验：`schemas/*.schema.json` 是字段唯一来源（spec 只解释语义），`scripts/validate.py` 用 jsonschema + 跨文件语义检查；默认校验当日 `work/` 产物，`--all` 校验最近一个含阶段产物的 work 日期目录（跳过只有 tokens.json 的目录），`--file` 可单独校验。
- 校验重试：任一阶段校验失败 → 主代理把错误清单回传给同一子代理（脚本则重跑脚本），最多 3 次尝试；第 3 次仍失败即终止任务，保留产物供诊断。
- 质量评分：`.opencode/plugins/quality-score.js` 在**子代理会话**的 `write`/`edit` 命中 `organize.json` 后调用 `scripts/score.py`（Python，确定性启发式），写 `work/YYYY-MM-DD/score.json` 并把评分卡追加到工具结果尾部。opencode 插件入口须为 JS，打分逻辑全部在 Python；等级阈值、维度权重、长度档位与词表见 `config/score-rules.json`；标签维度只看标签个数，不再读固定主题表。
- 需求边界：打回与 3 次终止是原始需求（只要求打分与展示）之外的扩展，用于守质量下限；若需回退，删除本节打回环即可。
- 打回：`score.json` 中任一条目 <60 即 `pass=false`；主代理带「低分条目 + 五维明细 + 命中空洞词」续派分析（只重写这些条目的 `core`/`why`）→ 整理（只重写这些条目的文字）→ 校验 → 打分。**按条目计次**：同一条目连续 3 次 <60 即终止任务、不写日报，保留全部产物与 `score.json` 的 `attempts[]` 分数轨迹。
- token 统计：`.opencode/plugins/token-stats.js` 监听 `message.updated`（assistant 已完成消息）按 `sessionID → 根会话 → agent` 聚合，写 `work/YYYY-MM-DD/tokens.json`，同日多轮按 `runs[]` 追加；同时写 `daily-knowledge/tokens/YYYY-MM-DD.md`。主代理收尾时读取并输出统计表，但不写入日报正文。
- 数据与版本控制：`work/`（仅放行每日 `work/*/collect.json`）、`.venv/`、`__pycache__/` 忽略；`daily-knowledge/`（日报 + token 报告）、`scripts/`、`schemas/`、`config/`、`.opencode/`、`.agents/`、`tests/`、`pyproject.toml`、`uv.lock` 纳入版本控制。`.gitignore` 用逐层例外只放行 `collect.json`，避免父目录被整目录忽略。
- 规范来源：本 spec 是工作流细则的单一来源；字段与形状以 `schemas/` 为准；`AGENTS.md` 只保留入口级约束与指针。

## 子代理设计

两个子代理定义在 `.opencode/agent/`，均为 `mode: subagent`、`hidden: false`——可被主代理自动委派，也可 `@` 手动单跑调试。流程细节由 `.agents/skills/` 下两个技能承载：

| 技能 | 阶段 | 对应子代理 |
| --- | --- | --- |
| `knowledge-analyze` | 分析 | `knowledge-analyze` |
| `knowledge-organize` | 整理 | `knowledge-organize` |

采集不再是子代理：`knowledge-collect` 的 agent 与技能已删除，由 `scripts/collect.py` 取代。

### 命名与模型

| 子代理 | 阶段 | 模型 | 温度 |
| --- | --- | --- | --- |
| `knowledge-analyze` | 分析 | `oc-go/deepseek-v4.1-flash` | 0.1 |
| `knowledge-organize` | 整理 | `oc-go/deepseek-v4.1-flash` | 0.4 |

不指定模型时会继承主代理。

### 工具与技能分工

- agent frontmatter：`name`、`description`（写清何时委派）、`mode`、`model`、`temperature`、`permission`、`hidden`。
- agent 正文是壳：一句话角色 + 「先用 skill 工具加载对应技能，再严格按技能执行」；技能加载失败时按失败模板返回。
- 技能 frontmatter：`name`、`description`（写清何时加载）、`allowed-tools`（按最小权限列必要工具并对路径/域名收敛；opencode 忽略该字段，实际限制由 agent `permission` 执行）。
- 技能正文必须包含：使用场景、输入、执行步骤、输出契约、失败模式、正反向自测与权限边界。
- 插件：`quality-score.js`（校验 + 打分）、`token-stats.js`（用量聚合）；插件只做转发与展示，判定口径在 Python 脚本里。

### 权限（最小权限）

- 用 `permission` 字段表达（`tools` 字段已废弃）；每个子代理以 `"*": deny` 兜底，再显式白名单。
- 权限路径 pattern 相对于 worktree 根目录（如 `work/**`；Windows 下大小写不敏感）。
- 技能加载按 agent 收口：每个子代理的 `skill` 只放行本阶段技能；`opencode.json` 顶层 `permission.skill` 对 `knowledge-*` deny，主代理不能自行加载流程技能。
- 能力矩阵：
  - 分析：读 spec/AGENTS.md、`work/`、`daily-knowledge/`；写 `work/**`；glob、grep、webfetch、todowrite 允许；skill 仅 `knowledge-analyze`；bash/task/question/websearch 禁止。
  - 整理：读 spec/AGENTS.md、`work/`、`daily-knowledge/`；写 `work/**`；todowrite 允许；不抓取网页；skill 仅 `knowledge-organize`；bash/task/question/websearch 禁止。
- 主代理（build）负责执行采集/校验/评分脚本、委派两个子代理、渲染日报，因此需要 bash/read/write/edit/task。
- 全部子代理禁止访问项目外目录，禁止向用户提问。

### 内容分工

- 分析段：打标签、去重、写 `core`（分析要点，承载理由与支撑事实）与 `why`（评价与建议）。
- 整理段：定稿条数与排序、压缩并润色 `core`、润色 `why`、写概览。
- 渲染段：只排版，不改字。

### 失败语义

- 完成标志：正式 JSON 完整写出并通过校验；失败时不落正式文件，已抓数据可写 `<阶段>.partial.json` 仅供人工诊断（主代理与续跑忽略）。
- 采集脚本失败：退出码非 0，stderr 给出原因；不写正式 collect.json。
- 子代理失败：返回统一失败摘要；主代理按重试规则处理。
- 校验失败：错误清单回传，最多 3 次。
- 打分打回：按条目最多 3 次；耗尽即终止，不写日报。
- 新进展核查失败：保守视为无进展（不计入失败）。
- 同日覆盖确认由主代理在委派整理前完成；CI 由工作流在启动 opencode 前按 `force` 判断跳过或覆盖。整理子代理直接覆盖写入。
- CI 无头运行：主代理不得向用户提问；任何需要用户决策的分支按失败处理，并保留已产出文件供 artifact 上传。

## 数据契约

字段与形状以 `schemas/` 为唯一来源；本节说明语义。JSON 为 UTF-8，`collected_at` 为本地时间（UTC+8，格式 `YYYY-MM-DD HH:mm`）。

### collect.json（采集脚本产物）

`schemas/collect.schema.json`：`date`、`collected_at`、`github[]`（collect 字段：full_name/url/description/language/stars_total/stars_today/stars_today_source/forks/created_at/pushed_at）、`gaps[]`。

- `github` 条数 ≤20（通常 15–20），按 `stars_today` 降序，不含 null。
- `gaps` 如实记录抓取异常、字段缺失、未纳入候选数量与 star_history 调用次数。

### analyze.json（分析子代理产物）

`schemas/analyze.schema.json`：

```jsonc
{
  "date": "YYYY-MM-DD",
  "github": [
    {
      "...collect.github 全部字段...",
      "themes": ["AI 代理", "开发工具"],
      "repeat": null,
      "core": "分析要点（不设 100 字硬限）",
      "why": "一句评价与建议"
    }
  ],
  "stats": { "github_count": 18, "dropped_recent_duplicates": 4 },
  "gaps": []
}
```

- 不含 `rank`、`overview`、`dropped_by_organize`。
- `themes` 为自由标签数组，非空字符串即可，不再校验固定主题表；建议每条 2–4 个。空数组表示「未打标签」（日报渲染为 `[其他]`）。
- `repeat`：仅历史出现过才有，形如 `{ "last_seen": "YYYY-MM-DD", "new_progress": "一句新进展 | null" }`；`last_seen` 必须真实存在于 `daily-knowledge/` 历史；`new_progress` 仅 30 天窗口内条目可写。
- 30 天窗口内历史条目须有新进展才保留（无法判定视为无进展，剔除并计入 `dropped_recent_duplicates`）；30 天外照常保留并标 `repeat`。

### organize.json（整理子代理产物）

`schemas/organize.schema.json`：

```jsonc
{
  "date": "YYYY-MM-DD",
  "github": [
    {
      "...analyze.github 全部字段...",
      "rank": 1,
      "core": "≤100 个汉字成稿",
      "why": "一句评价与建议"
    }
  ],
  "overview": {
    "lead": "今日一句总述",
    "themes": [{ "name": "AI 代理", "note": "该组当日要点一句" }]
  },
  "stats": {
    "github_count": 18,
    "dropped_recent_duplicates": 4,
    "dropped_by_organize": 1
  },
  "gaps": []
}
```

- `rank` 为 `1..N` 连续整数，顺序与 `stars_today` 降序一致。
- 条目数 15–20（不足按实际）；`dropped_by_organize` = analyze 条目数 − organize 条目数。
- `core` ≤100 个汉字（不计英文单词与数字）；`why` 独立一句。
- `overview.themes` 只含当日命中的分组（0 命中省略）；整理阶段把自由标签合并为不超过 6 组，`name` 为标签或合并后的组名。
- 事实字段（star、日期、链接、`themes`、`repeat`）照抄 analyze，不得改写；整理只负责合并分组写进概览，不回改条目标签。

### score.json（质量评分产物）

由 `scripts/score.py` 写入当日 work 目录：

```jsonc
{
  "date": "YYYY-MM-DD",
  "scored_at": "YYYY-MM-DD HH:mm",
  "file": "work/YYYY-MM-DD/organize.json",
  "attempt": 1,
  "valid": true,
  "items": [
    {
      "rank": 1,
      "full_name": "owner/repo",
      "total": 82,
      "grade": "A",
      "dimensions": {
        "summary": { "score": 20, "max": 25, "notes": [] },
        "depth": { "score": 18, "max": 25, "notes": [] },
        "format": { "score": 16, "max": 20, "notes": [] },
        "tags": { "score": 13, "max": 15, "notes": [] },
        "filler": { "score": 15, "max": 15, "notes": [] }
      },
      "filler_hits": []
    }
  ],
  "summary": {
    "average": 78.4,
    "grades": { "A": 3, "B": 4, "C": 1 },
    "below_min": ["owner/repo"],
    "pass": false
  },
  "pass": false,
  "attempts": [
    { "attempt": 1, "scored_at": "YYYY-MM-DD HH:mm", "valid": true, "pass": false, "content_hash": "<organize.json 的 sha256>", "items": [] }
  ]
}
```

- `attempts[]` 保留历次打回分数轨迹，每次评分追加一条；`content_hash` 用于识别同一份产物，内容未变时只刷新时间、不新增计次，主代理据此判为无进展、不无限打回。
- 校验不通过时不打分：`valid=false`、`pass=false`、`errors[]` 给出校验错误，且不计入 `attempts[]`。
- 等级：A≥80、B≥60、C<60；`pass` 当且仅当所有条目 ≥60。
- 「标签精度」按标签个数给分：2–4 个满分，1 个中档，≥5 个降档，0 个 0 分；具体分值与上限见 `config/score-rules.json`，不再依赖固定主题表或关键词证据。

### tokens.json（用量产物）

由 token 插件写入当日 work 目录：`date`、`updated_at`、`runs[]`；每个 run 含 `root_session`、`started_at`、`updated_at`、`agents{}` 与 `total{}`；每个 bucket 含 `messages/input/output/reasoning/cache_read/cache_write/cost`。同日多轮追加，不覆盖。

同时由同一插件生成 `daily-knowledge/tokens/YYYY-MM-DD.md`：

```markdown
# Token 统计 · YYYY-MM-DD

## Run 1 · YYYY-MM-DD HH:mm – HH:mm

| 代理 | 消息数 | input | output | cache 读 | cache 写 | reasoning | cost(USD) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| build | … | … | … | … | … | … | … |
| knowledge-analyze | … | … | … | … | … | … | … |
| knowledge-organize | … | … | … | … | … | … | … |
| 合计 | … | … | … | … | … | … | … |

## 当日合计

| 消息数 | input | output | cache 读 | cache 写 | reasoning | cost(USD) |
| --- | --- | --- | --- | --- | --- | --- |
| … | … | … | … | … | … | … |
```

- 数值与 `tokens.json` 完全一致；不得改写、估算或补全缺失值。
- 无 run 或 `tokens.json` 不可读时不生成报告，由主代理在汇报中说明。

### 约定

- `work/` 原始数据全量保留、不做删减；仅每日 `collect.json` 进入 git，其余本地留存。
- 所有 JSON 产物写入后都应是「可被 `validate.py` 通过」的状态。

## 编排协议

四段由主代理（默认 build）编排；两个子代理各自只执行本阶段。

### 阶段与命令

1. **采集**：`uv run python scripts/collect.py --date <日期>` → `validate.py --file work/<日期>/collect.json`。
2. **分析**：Task 委派 `knowledge-analyze` → `validate.py --file work/<日期>/analyze.json`。
3. **整理**：Task 委派 `knowledge-organize` → `validate.py --file work/<日期>/organize.json` → 读 `score.json` 判定是否打回。
4. **渲染**：主代理按模板写 `daily-knowledge/<日期>.md`；token 插件已生成 `daily-knowledge/tokens/<日期>.md`。
5. **汇报**：读 `tokens.json`，输出 token 统计表，并确认 token md 已生成。

### 委派

- 用 Task 工具依次委派 `knowledge-analyze` → `knowledge-organize`，上一段完成并通过校验后才委派下一段。
- 委派消息模板：`阶段：<分析|整理>；日期：YYYY-MM-DD；产物：<work/YYYY-MM-DD/analyze.json | work/YYYY-MM-DD/organize.json>；打回条目：<无 | 清单>。先加载技能 <knowledge-analyze|knowledge-organize>，再按其「输入」与「执行步骤」执行；数据契约见 .scratch/knowledge-daily/spec.md 与 schemas/。`
- 完成判定：产物文件存在且 `validate.py` 通过（字段级，不深度判断文笔）。
- 保留每次 Task 返回的 `task_id`，重试与打回时用它续跑同一子代理会话。

### 校验环

- 每阶段独立计数，最多 3 次尝试（采集脚本同样适用）。
- 校验失败：主代理把 `validate.py` 的错误清单原样附在续问里，用同一 `task_id` 续跑；采集脚本则重跑命令并展示 stderr。
- 不删除已写产物（重跑直接覆盖）；第 3 次仍失败即终止任务，保留产物，报告失败清单。
- 断点续跑时计数清零。

### 打分环与打回

- 整理子代理每次写 `organize.json`，`quality-score.js` 自动校验并打分，写 `score.json`，评分卡追加到工具结果尾部（子代理只读，不自行回改）。
- 主代理读 `score.json`：`pass=true` 进入渲染；`pass=false` 则按 `summary.below_min` 发起打回。
- 打回流程：带上「低分条目 + 五维明细 + 命中空洞词 + 低分原因」续派 `knowledge-analyze`（只重写这些条目的 `core`/`why`）→ 续派 `knowledge-organize`（只重写这些条目的文字与必要的概览调整）→ 校验 → 打分。
- **按条目计次**：同一条目连续 3 次 <60 即终止任务；终止时不写 `daily-knowledge/`，保留 `work/` 全部产物与 `score.json`，报告卡住条目与卡在哪一维。
- 未打回的条目原样保留，不重算、不改顺序；已被剔除的条目不复活。

### 渲染模板（主代理机械填充）

```markdown
# 知识日报 · YYYY-MM-DD

> 质量评分：均分 X · A a / B b / C c

## 今日概览

{overview.lead}

- **{theme.name}**：{theme.note}

## GitHub 趋势

### {rank}. {full_name}

- 标签：[{theme1}] [{theme2}]
- Star：{stars_total}（今日 +{stars_today}）· 评分：{score.total} / {score.grade}
- 🔁 重复：上次 {repeat.last_seen}
- 新进展：{repeat.new_progress}
- 链接：{url}
- 核心内容：{core}
- 为什么值得关注：{why}
```

- `overview.themes` 按 organize 中的顺序逐条输出；条目的 `themes` 为空数组时输出 `[其他]`。
- Star 总数用千分位，今日新增照抄 `stars_today`（含 0）。
- 逐条评分按 `score.json.items[]` 的 `rank` 与 `full_name` 对齐；`score.json` 缺失或 `valid=false` 时省略该条评分部分与标题下均分行，并在汇报中说明。
- 无 `repeat` 时省略那两行；有 `repeat` 但 `new_progress` 为 null 时只留「🔁 重复」一行。
- 除模板占位符外不增删段落，不改写任何文字与数字。

### token 汇报（收尾）

主代理读 `work/<日期>/tokens.json`，汇总所有 runs 在对话中输出，并确认 `daily-knowledge/tokens/<日期>.md` 已存在：

| 代理 | 消息数 | input | output | cache 读 | cache 写 | reasoning | cost(USD) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| build（主代理） | … | … | … | … | … | … | … |
| knowledge-analyze | … | … | … | … | … | … | … |
| knowledge-organize | … | … | … | … | … | … | … |
| 合计 | … | … | … | … | … | … | … |

- 统计不含主代理最后一条回复（该消息在汇报之后才完成）。
- `tokens.json` 缺失或不可读时，汇报「统计不可用」并说明插件可能未加载，不猜测数字。

### 断点续跑（「继续知识采集」）

| 现状 | 动作 |
| --- | --- |
| 无 collect.json | 从采集开始 |
| 有 collect.json、无 analyze.json | 从分析开始 |
| 有 analyze.json、无 organize.json | 从整理开始 |
| 有 organize.json、无 score.json | 重新打分后继续 |
| score.json 存在且 pass=false（未耗尽 3 次） | 从打回开始 |
| score.json pass=true、无当日 daily-knowledge | 从渲染开始 |
| 当日 daily-knowledge 已存在 | 本地：询问三选一；CI：`force=false` 跳过，`force=true` 覆盖 |

不重跑已完成阶段。

### 同日重跑（当日 daily-knowledge 已存在）

本地由主代理提示并让用户三选一，默认第一项；CI 在启动 opencode 前判断：`force=false` 直接跳过并退出 0，`force=true` 选第一项。

1. **重新采集并覆盖**：重跑采集 → 分析 → 整理 → 渲染（当日 work 数据被新数据覆盖，token 历史保留）。
2. **仅重写日报**：保留 work 当日数据与评分，只重渲染 `daily-knowledge/`。
3. **取消**：什么都不做。

### 失败处理与恢复

- 子代理失败：本地由主代理向用户报告原因与建议后停止；用户说「继续知识采集」时按断点续跑。CI 直接失败、上传 artifact，不提交半成品、不重试。
- 单阶段手动触发（`@knowledge-analyze` 等）允许用于调试；前置产物缺失时该阶段应以前置缺失失败，而非自动重跑前段。
- 强制重跑某阶段：删除 `work/YYYY-MM-DD/` 下对应产物文件（或 `daily-knowledge/` 当日文件）后重新触发；打回计次存于 `score.json`，删除它即清零。

## 测试决策

### 好测试的标准

只断言外部可观察行为：命令退出码、stdout/stderr、写出的 JSON/MD 内容，以及产物之间的一致性。测试把「日期目录里的输入」喂给脚本，断言产物是否满足契约；不 import 脚本内部函数、不断言实现细节，也不测子代理的文笔。

### 唯一的测试 seam

**脚本 CLI + 产物文件**。`collect` / `validate` / `score` 三个命令是唯一 seam，覆盖采集选取、契约校验、跨文件语义（rank 连续、core 字数、repeat 历史、剔除计数）、评分/等级/attempts 与自由标签；不新增模块级 seam。

- 真实网络不纳入测试：`tests/fixtures/` 保存 GitHub 的真实返回快照（搜索 + star 历史，注明抓取日期），测试用本地 HTTP 服务器回放，经 `KNOWLEDGE_GITHUB_API` 指向；覆盖响应形状解析、`IncompleteRead` 重试与无凭证守门。
- `work/` 与 `daily-knowledge/` 用 `KNOWLEDGE_WORK_DIR` / `KNOWLEDGE_OUTPUT_DIR` 指向临时目录，测试不读写真实目录；重命名后环境变量名保持不变。
- 插件不为新行为新建 seam：`quality-score.js` 仍只转发评分；`token-stats.js` 新增的 token md 属确定性排版，由端到端验收观察（文件存在、表格数值与 `tokens.json` 一致），不做 JS 单测。
- GitHub Actions 不新建 seam：工作流语法由 GitHub 解析；在临时 `ci-smoke` 分支用真实 `workflow_dispatch` 验收（`force=true` 全流程、`force=false` 跳过、失败上传 artifact），跑通后才合并 `main`；不引入 `act` 或本地 runner 作为替身。
- 端到端仍只做人工验收：一次真实本地运行 + 一次真实 CI 运行，检查日报、评分卡、token md 与提交内容。

### 被测模块

- 采集脚本：无凭证守门（且不发请求）、fixture 回放下的 star 历史解析、响应中断重试、`--date` 落盘与 `collected_at` 格式、按今日新增 star 降序、候选不足时写入 `gaps`、上一自然日 `collect.json` 的本地差分。
- 校验脚本：三份契约的正反例（未知字段、类型错误、date 与目录不一致、rank 不连续、计数不一致、repeat 历史不存在、`themes` 元素类型非法）；自由标签与非固定主题被接受，空 `themes` 可接受；不再有主题白名单用例；`--all` 跳过只有 tokens.json 的日期目录。
- 评分脚本：五维得分、A/B/C 阈值、`pass` 判定、`attempts[]` 追加、校验失败时跳过分、标签个数分档（0 / 1 / 2–4 / ≥5）。
- 不测：插件内部排版、子代理提示词与文笔、GitHub 真实网络、GitHub Actions runner。

### 先例

- `uv run python -m unittest discover -s tests -t .` 覆盖：fixture 解析、`IncompleteRead` 重试、无凭证守门、`--all` 目录选择。
- 已用变异验证测试能红：去掉重试、让 star 历史解析返回 null、`--all` 只看最新目录，三种改动各自使对应测试失败。
- `validate.py` 对 `work/2026-10-09`、`work/2026-10-11` 的历史 collect.json 校验通过。
- 合成 organize.json 样本（含 A/B/C 条目、repeat、overview）跑通 validate + score，并验证第二次打分 attempt 递增。
- 自由标签用例：任意非空标签与空数组均通过校验；评分只随标签个数变化。
- 改名回归：把 `KNOWLEDGE_OUTPUT_DIR` 指向含历史日报的临时目录，repeat 历史校验与 `--all` 仍通过。
- 仓库已用 `unittest` 覆盖采集脚本的 CLI 行为（`test_collect.py`、`test_validate_all.py`）；子代理文笔、插件排版与 CI 行为仍以人工验收为主。

### 端到端验收清单

- 脚本自测（可手工跑）：
  - `uv run python scripts/validate.py --date YYYY-MM-DD`：当日产物全部通过。
  - `uv run python scripts/validate.py --all`：最近一个含阶段产物的 work 日期目录通过。
  - `uv run python scripts/collect.py --date YYYY-MM-DD --dry-run`：输出合法 collect JSON（不落盘）。
  - 去掉 `GITHUB_TOKEN`（进程环境与 `.env` 都为空）跑同一命令：应立即失败并提示配置位置，且不发任何网络请求。
  - `uv run python scripts/score.py --date YYYY-MM-DD`：输出评分卡与 `score.json`。
- 每次产出后可抽查的验收点：
  - 结构完整：日期标题、质量评分摘要、今日概览（一句总述 + 分组要点）、GitHub 趋势齐全；条目格式符合模板。
  - 数量与排序：GitHub 趋势 15–20 条（或 gaps 说明不足）、按 `stars_today` 降序、`rank` 连续。
  - 标签自由：条目标签不再限定固定主题；每条建议 2–4 个；未打标签的渲染为 `[其他]`；概览分组不超过 6 组。
  - 展示齐全：每条含总 star（千分位）、今日新增 star 与评分/等级；标题下含均分与 A/B/C 分布；评分缺失时只省略评分部分。
  - 篇幅：每条核心内容 ≤100 个汉字。
  - 去重可核查：每个 🔁 标记中的日期在 `daily-knowledge/` 历史中确实存在；30 天内无新进展的旧条目未出现。
  - 可追溯：work/YYYY-MM-DD/ 的 collect/analyze/organize/score 覆盖当天全部产出条目；当日 `collect.json` 已提交。
  - 评分可见：整理子代理写文件后工具结果带评分卡；`score.json` 含五维、等级与 `attempts[]`；标签维度按个数计分。
  - 打回生效：单条 <60 时 analyze/organize 被重新委派，且重写范围仅限低分条目。
  - token 汇报：收尾出现分代理统计表，数字与 `tokens.json` 一致；`daily-knowledge/tokens/<日期>.md` 存在且数值一致。
- CI 冒烟（临时分支 `ci-smoke`，需先配置 `OC_GO_API_KEY`；跑通后才合并 `main`）：
  - 当日日报已存在且 `force=false`：工作流跳过、退出 0，不产生新提交。
  - `force=true`：重新采集并覆盖，提交 `daily-knowledge/<日期>.md`、`daily-knowledge/tokens/<日期>.md` 与 `work/<日期>/collect.json`。
  - 失败：工作流标红、artifact 含 `work/<日期>/`、仓库中最后一份日报未被改写。
  - 凭证：日志中不出现 `OC_GO_API_KEY` 明文；`GITHUB_TOKEN` 只用于采集与推送。
- 子代理、技能与插件可观察性：`opencode debug agents` 可见两个 subagent，且各自 `skill` 只放行本阶段技能、主代理侧 `knowledge-*` 为 deny；`.agents/skills/` 下两份 SKILL.md 的 frontmatter 合规；插件启动无报错。
- 失败行为：前置产物缺失时，委派对应子代理应以「前置缺失」失败且不产出正式文件；连续 3 次校验失败或条目 3 次低分应终止且不发日报。

## 范围外

- 除 GitHub Actions 之外的调度方式（其他 CI、系统 cron、云函数）。
- 除采集、校验、评分与两个插件外的其他脚本。
- 发布站点：不做 GitHub Pages、RSS 或站内索引，只把 markdown 提交进仓库。
- 通知渠道：失败不自动开 issue，不发邮件或 IM。
- 自动重试：CI 失败不自动重跑。
- LLM 打分：评分保持确定性启发式，不引入模型判定。
- 采集源扩展：当前仅 GitHub，不接 Hacker News 或其他站点。
- issue tracker 的完整配置（triage labels、domain docs）：本次只落地最小 tracker 配置。

## 备注

- 固定主题表已移除，标签由分析阶段自由生成；若将来需要引导，在技能正文里加「标签建议」，不要恢复白名单。
- 自动运行配置：在 GitHub 仓库 `Settings → Secrets and variables → Actions` 添加 `OC_GO_API_KEY`；定时为 `0 0 * * *` UTC（08:00 UTC+8）；手动 dispatch 的 `force` 用于覆盖当天。
- 本地首次推送使用 `~/.ssh/git`；CI 使用自带 `GITHUB_TOKEN`，不需要 Personal Access Token。
- 首次启用 CI 前先把历史日报迁到 `daily-knowledge/`，否则去重与概览历史为空。
- 本次变更建议补两条 ADR：自由标签取代固定主题、GitHub Actions 无头运行流水线。
- 实现时同步更新 `AGENTS.md`（目录、自动运行、凭证）、`GLOSSARY.md`（自由标签、token 报告）、两个技能（不再读 `topics.md`、历史目录改为 `daily-knowledge/`）与 `config/score-rules.json`（标签个数分档）。
- 本 spec 落在 local markdown tracker：`.scratch/knowledge-daily/spec.md`；tracker 配置见 `docs/agents/issue-tracker.md`。
- 术语见根目录 `GLOSSARY.md`；难以反悔的技术取舍见 `docs/adr/`。
- 采集凭证的获取与配置步骤见 `AGENTS.md`「凭证」，模板见 `.env.example`。
- Python 依赖由 `uv` 管理（`pyproject.toml` + `uv.lock`），运行入口统一为 `uv run python …`。
