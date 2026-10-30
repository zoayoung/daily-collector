# 知识采集系统 · 需求规格

**Feature:** knowledge-daily
**Status:** ready-for-agent
**Updated:** 2026-10-30

## 问题陈述

每天要在 GitHub 上冒头的新项目很多：手动浏览耗时、容易漏掉重点；只看累计 star 分不清「今天真正在涨」的项目。当前流水线虽然每天扫描约 100 个候选，但 `collect.json` 只写 20 个，最终日报常不足 15 个；同时 30 天去重留了「有新进展可突破」的口子，补丁版本也被当成新进展，导致昨天刚出现过的项目今天再次出现。候选池按累计 star 排序，天然被巨型老项目占满；star 历史兜底只有 20 次，又让大部分候选算不出数据归属日增量。固定 6 个关注主题已取消，但上述限制叠加后，读者仍会觉得「项目又少又重复」。

需要一个能每天自动发布的工作流：采集由脚本确定性完成以省成本，分析与整理交给子代理以保证判断与文笔，产出中文知识日报并长期积累；同时用 schema 校验、确定性质量评分与 token 统计，让产物的「对不对」「好不好」「花了多少」都可见。日报要能展示单条评分与项目总 star，成本要有一份人可读的 markdown，产物要能每天提交到公开仓库。

## 方案

- 用户说「开始今天的知识采集」，一次跑完 **采集 → 分析 → 整理 → 渲染** 四段，并汇报 token 成本。本地与 GitHub Actions 共用同一套步骤；CI 定时任务以「开始知识采集；发布日 YYYY-MM-DD；数据归属 YYYY-MM-DD」触发，发布日为运行日，数据归属为前一日（UTC+8）。
- **采集（Python 脚本，必须使用采集凭证）**：按多个 star 区间与新仓库通道分别搜索、按 `full_name` 去重得到约 1000 个唯一候选（star 区间约 800，其余来自近 30 天新建）；先用已发布日报过滤 30 天窗口内的项目，再逐个算出「数据归属日新增 star」，按它降序写入前 50 条到 `collect.json`。
- **分析（子代理）**：只做内容分析——自由打标签（不受固定主题表约束）、给 30 天外再次出现的项目标 `repeat.last_seen`、写分析要点与评价，写 `analyze.json`；不再自行剔除 30 天内项目。
- **整理（子代理）**：职责分离后的定稿者——从分析结果中定稿 10–15 条、润色为成稿、定排序与概览，写 `organize.json`；批量剔除时记数并按批次说明理由。
- **渲染（主代理）**：按固定模板把 `organize.json` 机械填充为 `daily-knowledge/YYYY-MM-DD.md`，不改写文字；每条附总 star、数据归属日新增 star 与质量评分。
- **质量与成本**：`schemas/` 是字段唯一来源，`scripts/validate.py` 做契约校验与 30 天窗口硬校验；`.opencode/plugins/` 的 hook 在整理产物落盘后调 `scripts/score.py` 做 5 维打分并写 `score.json`，低于 60 分打回重来；token 插件聚合消耗，同时写 `daily-knowledge/tokens/YYYY-MM-DD.md` 供人阅读。
- **自动发布（GitHub Actions）**：每天清晨 06:00（UTC+8）起两班非整点抢发，无头运行同一套流水线，发布当天（UTC+8）的日报、数据归属于前一日，目标 08:00 前完成；把日报、token 报告与每日 `collect.json` 提交回公开仓库 `zoayoung/daily-collector` 的 `main` 分支。
- 中间产物按天落在 `work/YYYY-MM-DD/`（仅每日 `collect.json` 进 git，其余本地保留）。

## 用户故事

1. 作为用户，我希望用一句固定触发语启动当天采集，以便不用记忆复杂命令。
2. 作为用户，我希望一次触发自动跑完采集→分析→整理→渲染，以便中途无需人工介入。
3. 作为用户，我希望失败后说「继续知识采集」从断点续跑，以便不浪费已完成的阶段。
4. 作为用户，我希望同日重跑时先收到提示并三选一（重新采集并覆盖 / 仅重写日报 / 取消），以便按需刷新数据或只修补日报。
5. 作为用户，我希望日报文件名按发布日（UTC+8）归属；定时任务的数据归属为发布日前一天，并在报告内部标注，以便早上读到刚结束那天的完整数据。
6. 作为读者，我希望采集只依赖 GitHub 一个数据源，以便口径单一、维护简单。
7. 作为维护者，我希望采集由 Python 脚本完成而不是子代理交互抓取，以便口径可复现、token 成本可预期。
8. 作为维护者，我希望采集脚本必须携带 `GITHUB_TOKEN` 认证运行，以便配额稳定、口径可预期。
9. 作为读者，我希望用 GitHub 搜索 API 拉候选：star 区间通道取「近 1 日有推送、累计 star≥100」，新仓库通道取「近 30 天创建、累计 star≥50」，以便同时覆盖活跃老项目与刚发布的新爆款。
10. 作为读者，我希望按「数据归属日新增 star」排序，以便看到当天真正在涨的项目。
11. 作为读者，我希望数据归属日新增 star 优先用本地历史差分、无历史时用官方 star 历史接口兜底，以便在零额外成本与准确性之间取平衡。
12. 作为读者，我希望两次都拿不到星增量时如实记 null、不编造，以便数据可信。
13. 作为读者，我希望每轮 star 历史兜底调用不超过 150 次，以便在扩大候选覆盖的同时控制抓取耗时与配额消耗。
14. 作为分析者，我希望采集字段齐全（全名、描述、语言、总 star、数据归属日新增 star、fork、链接），以便后续阶段不必回头补抓。
15. 作为维护者，我希望原始数据全量保留在 work/、不做删减，以便随时复查。
16. 作为读者，我希望日报每日输出 10–15 个项目，以便篇幅稳定又不冗长。
17. 作为读者，我希望每个项目带上自由标签，以便一眼看出它涉及哪些技术方向。
18. 作为读者，我希望一个项目可命中多个标签，以便标签如实反映内容。
19. 作为读者，我希望未打标签的项目标 `[其他]`，以便不遗漏高价值内容。
20. 作为读者，我希望 30 天内出现过的项目一律不再输出，以便不重复看到旧内容。
21. 作为读者，我希望重复窗口按滚动 30 天计算且不含今天，以便同日重跑仍可刷新当天内容。
22. 作为读者，我希望 30 天外再次出现的项目照常输出并标记「🔁 重复：上次 YYYY-MM-DD」，以便知道它再次出现。
23. 作为读者，我希望 30 天外重复项不再要求写「新进展」，以便规则简单、可判定。
24. 作为分析者，我希望分析阶段只负责标签、重复标注与内容判断，不再剔除 30 天内项目，以便去重口径唯一且确定性。
25. 作为整理者，我希望在分析结果之上定稿 10–15 条，以便按当天节奏控制篇幅。
26. 作为维护者，我希望整理阶段批量剔除时记数并按批次说明理由，以便事后追查。
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
65. 作为维护者，我希望关注面不受固定主题表限制，以便系统不静默缩小采集与展示范围。
66. 作为读者，我希望每条项目显示总 star 与数据归属日新增 star，以便同时判断体量与当天热度。
67. 作为读者，我希望每条项目显示质量评分与 A/B/C 等级，以便知道系统为什么认为它写得好或不好。
68. 作为读者，我希望标题下保留均分与等级分布，以便一眼看到当天整体质量。
69. 作为读者，我希望评分不可用时省略评分部分而不是编造数字，以便数据始终可信。
70. 作为读者，我希望 star 数字带千分位，以便大数字快速可读。
71. 作为读者，我希望日报存放在 `daily-knowledge/`，以便目录名直接说明内容。
72. 作为维护者，我希望历史日报位于 `daily-knowledge/`，以便去重与重复标记准确。
73. 作为维护者，我希望路径常量、校验、测试与文档共用一套路径口径，以便仓库里只有一种存放位置。
74. 作为读者，我希望 token 报告以 markdown 存在 `daily-knowledge/tokens/YYYY-MM-DD.md`，以便直接阅读。
75. 作为读者，我希望 token 报告按 run 与代理拆分并给出当日合计，以便定位成本大头。
76. 作为维护者，我希望 token 报告在每次运行后自动生成，以便不靠手工整理。
77. 作为维护者，我希望 token 报告随日报一起提交，以便成本历史与产出放在同一处。
78. 作为维护者，我希望流水线每天清晨 06:00（UTC+8）起由 GitHub Actions 自动运行、08:00 前完成并发布当天日报（数据归属前一日），以便不需要每天手工触发。
79. 作为维护者，我希望同一套流水线仍能在本地手动触发，以便调试与补跑。
80. 作为维护者，我希望 CI 复用采集、分析、整理、渲染四段，以便线上与本地行为不分叉。
81. 作为维护者，我希望 CI 在发布日日报已存在时跳过，以便定时任务幂等。
82. 作为维护者，我希望手动触发时可以强制覆盖当天，以便刷新数据或修补日报。
83. 作为维护者，我希望 CI 先跑单元测试再调用模型，以便契约问题不消耗 token。
84. 作为维护者，我希望 CI 失败时上传 `work/` 产物，以便下载现场排查。
85. 作为维护者，我希望 CI 失败后不自动重试，以便不重复烧钱。
86. 作为维护者，我希望 CI 把 `daily-knowledge/` 与每日 `collect.json` 提交回仓库，以便历史、去重与 star 差分持续可用。
87. 作为维护者，我希望除每日 `collect.json` 外的 `work/` 不进入 git，以便仓库不随天数膨胀。
88. 作为维护者，我希望模型密钥只存在于仓库 Secret，以便公开仓库不泄露凭证。
89. 作为维护者，我希望 CI 锁定 opencode 版本与模型，以便每天运行可复现。
90. 作为读者，我希望公开仓库每天出现一份新日报，以便不装本地工具也能阅读。
91. 作为维护者，我希望仓库包含历史日报，以便去重与趋势从第一天就完整。
92. 作为维护者，我希望默认分支为 `main`，以便与新仓库一致。
93. 作为维护者，我希望 CI 失败时最后一份已发布日报保持不变，以便发布质量不会被半成品污染。
94. 作为维护者，我希望 CI 只额外配置一个模型密钥，以便采集与回写都复用自带令牌。
95. 作为维护者，我希望 CI 在无头环境不向用户提问，以便定时任务不会卡住。
96. 作为维护者，我希望标签校验不依赖固定词表，以便新增标签无需改配置。
97. 作为维护者，我希望 CI 先在临时分支上真实跑通再合并 `main`，以便推送后定时任务第一次就能成功。
98. 作为维护者，我希望 CI 冒烟同时覆盖「当日已存在则跳过」与 `force` 覆盖两条路径，以便幂等行为经过验证。
99. 作为维护者，我希望采集阶段先过滤 30 天窗口内的项目再计算增量，以便不浪费 star 历史调用。
100. 作为维护者，我希望候选池按多个 star 区间分别搜索并按 `full_name` 去重，以便每月 300–450 个不重复项目有稳定来源。
101. 作为维护者，我希望每个 star 区间最多翻 2 页，以便控制搜索调用与耗时。
102. 作为维护者，我希望 star 历史兜底上限提高到 150 次/轮，以便扩大候选的增量覆盖率。
103. 作为维护者，我希望 `collect.json` 写入 50 条并按 `stars_today` 降序，以便次日本地差分覆盖更多项目。
104. 作为维护者，我希望 `collect.json` 新增可选的 `candidates`、`eligible`、`dropped_recent_duplicates` 统计，以便去重数量可核查，同时旧产物仍能通过校验。
105. 作为维护者，我希望 30 天窗口的判定同时由采集脚本与 `validate.py` 执行，以便规则不依赖子代理自觉。
106. 作为维护者，我希望 `validate.py` 对窗口内条目直接报错，不论是否有新进展，以便规则零例外。
107. 作为维护者，我希望 `repeat` 只保留 `last_seen`，以便契约与渲染模板简化。
108. 作为维护者，我希望没有 `stats` 的旧 `collect.json` 继续通过 `--all` 校验，以便历史产物不被追溯破坏。
109. 作为维护者，我希望配置拆分为 `collect_min_items`、`report_min_items`、`report_max_items`，以便采集与日报的下限各自可调。
110. 作为维护者，我希望日报条数低于 10 时只告警并按实际输出，以便不因候选不足而整天没有日报。

## 实现决策

- 系统形态：**采集脚本 + 分析子代理 + 整理子代理 + 主代理渲染**，由 GitHub Actions 定时运行。段间以 JSON 传递中间产物，按天落在 `work/YYYY-MM-DD/`。
- 本节之后的三节——子代理设计、数据契约、编排协议——同属实现决策的细则。
- 触发：本地固定触发语「开始今天的知识采集」；续跑语「继续知识采集」。CI 直接以同一触发语无头运行，不经过对话。
- 关注面：分析阶段自由打标签，不设固定主题白名单；`themes` 为空数组表示「未打标签」，日报渲染为 `[其他]`。
- 标签口径：每条建议 2–4 个标签；评分「标签精度」改为按标签个数给分（2–4 个满分、1 个中档、≥5 个降档、0 个 0 分），不再检查关键词证据。
- 概览口径：整理阶段把自由标签合并为不超过 6 组，再写 `overview.themes`；0 命中省略。
- 日报展示：每条元信息行固定为「Star：总数（今日 +增量）· 评分：总分 / 等级」；评分来自当日 `score.json`，按 `rank` 与 `full_name` 同时匹配；缺失处理与标题下行见「编排协议 · 渲染模板」。
- 产物目录：日报与 token 报告落在 `daily-knowledge/`，日报文件名为 `YYYY-MM-DD.md`；历史日报是该目录下的去重依据。默认目录可用 `KNOWLEDGE_OUTPUT_DIR` 覆盖。
- token 报告：`.opencode/plugins/token-stats.js` 在刷新 `work/YYYY-MM-DD/tokens.json` 后，同时写 `daily-knowledge/tokens/YYYY-MM-DD.md`；文件名取发布日，数据归属日与发布日不同时在正文标注统计窗口行（口径见「渲染模板」节）。内容按 run、按代理列出与 `tokens.json` 相同的字段，并给出当日合计。日期取 `KNOWLEDGE_DATE`，统计窗口依据 `KNOWLEDGE_GAIN_DATE`，未设置时取本地今天。
- 自动运行：GitHub Actions 在 22:07 与 22:47 UTC（06:07、06:47 UTC+8）各排一班，发布日为运行日，数据归属为运行日前一天（UTC+8）；目标窗口 06:00–08:00，`daily` 超时 45 分钟。GitHub 的 `schedule` 按 UTC 墙钟且为 best-effort：整点高负载时会被推迟数小时甚至整条丢弃，故用两班非整点抢发、靠幂等检查保证当天只发布一次；两班都被推迟时照常发布并在运行摘要标注「超窗」。`ubuntu-latest`；步骤为检出 → 计算发布日与数据归属日 → 安装 uv 与 Node → 同步依赖 → 跑单元测试 → 安装锁定版本的 opencode → 无头执行 `opencode run --auto "开始知识采集；发布日 <发布日>；数据归属 <数据归属日>"` → 校验产物 → 提交回写。
- CI 参数：opencode 以 `@opencode/cli@2.0.26` 安装（`opencode-ai` 是 1.x 包，勿混用），所有代理统一使用 `oc-go/deepseek-v4.1-flash`；仓库内 `opencode.json` 固定 provider `oc-go` 与默认模型，`apiKey` 用 `{env:OC_GO_API_KEY}` 占位。
- CI 凭证：模型密钥只放在仓库 Secret `OC_GO_API_KEY`；采集与回写共用 Actions 自带的 `GITHUB_TOKEN`（`permissions.contents: write`），不额外配置 Personal Access Token。
- CI 幂等：启动 opencode 前检查发布日 `daily-knowledge/<发布日>.md`；存在且 `force=false` 则跳过并退出 0，`force=true` 按「重新采集并覆盖」执行。定时任务的发布日为运行日、数据归属为前一天；手动 dispatch 的发布日与数据归属都是当天。两班定时与手动触发共用同一幂等检查，先到者发布、后到者跳过。
- CI 失败：不自动重试；把 `work/<发布日>/` 上传为 artifact，不提交半成品，最后一份已发布日报保持原样。
- CI 并发：同一 workflow 使用单一并发组，避免定时与手动触发重叠。
- CI 冒烟（交付门槛）：先在临时分支 `ci-smoke` 推送并 `workflow_dispatch` 真实跑通，覆盖 `force=true` 全流程与 `force=false` 跳过两种情形，再合并 `main`；不以 `act` 或本地 runner 代替真实 Actions。
- 发布仓库：`https://github.com/zoayoung/daily-collector`（public），默认分支 `main`；本地用 `~/.ssh/git` 推送；仓库包含历史日报与现有测试。
- 采集脚本：`scripts/collect.py`，由主代理用 `uv run python scripts/collect.py --date <发布日> --gain-date <数据归属日>` 执行；`--gain-date` 默认取 `KNOWLEDGE_GAIN_DATE`，再退回 `--date`；未给 `--date` 时依次取 `KNOWLEDGE_DATE` 与本地今天；`--dry-run` 打印 JSON 不落盘。脚本承担多查询候选池、30 天过滤、数据归属日新增 star、排序选取、`gaps` 与 `stats` 全流程，产物符合 `schemas/collect.schema.json`。
- 候选池口径：两条通道并列。① star 区间通道：按 4 个 star 区间（`100..500`、`500..2000`、`2000..10000`、`>10000`）分别搜索，保留 `pushed:>=` 约束（取发布日前一天），每个区间 `per_page=100`、最多 2 页（第一页不足 100 条则不再翻页）；老项目只要今日快速上升，同样是有效候选。② 新仓库通道：按 `created:>=` 发布日前 30 天、`stars:>=50` 搜索，`sort=stars`、`order=desc`、`per_page=100`、最多 2 页（第一页不足 100 条则不再翻页）；不加 `pushed` 约束，近 30 天新建但久未推送的项目也能入候选。两路结果合并后按 `full_name` 大小写不敏感去重，保留首次出现的原始大小写（star 区间通道先收集，重叠项目计入该通道）；随后统一经过 30 天重复窗口过滤与增量计算。唯一候选约 1000 个（star 区间约 800，其余来自新仓库通道）。通道标记只存在于采集脚本内部，不写入产物。
- 30 天重复窗口：以 `daily-knowledge/*.md` 中已发布的项目为准（读取 `### N. owner/repo` 标题行，大小写不敏感），窗口为 `[发布日-30, 发布日-1]`，**不含发布日**；窗口内出现过的项目零例外剔除。同日重跑不把发布日当天已发布内容当历史。
- 采集过滤与计数：候选先去重，再按 30 天窗口剔除，剩余为 `eligible`；`dropped_recent_duplicates` 记录被剔除数。`collect.json` 新增可选 `stats: { candidates, eligible, dropped_recent_duplicates, channels }`；`channels` 为可选对象 `{ star_bands, new_repos }`，两个非负整数，按去重后的候选数统计，满足 `star_bands + new_repos = candidates`，与 `candidates` 自洽；旧产物无 `stats` 或 `channels` 仍有效。
- 采集异常：未配置 `GITHUB_TOKEN`、所有搜索均失败、过滤后候选为空即脚本失败（退出码非 0、不写正式文件）；`star_history` 单次失败记 `gaps` 并把该条记 null。
- 新增 star 口径：基线取 `work/**/collect.json` 中**日期早于发布日的最近一次**该 repo 的 `stars_total`；仅当基线恰为**发布日的上一自然日**时才用于差分（同日重跑不会读到自身产物）。优先级：① 本地差分 `stars_today_source=local_diff`，命中者不消耗预算；② 官方兜底 `GET /repos/{owner}/{repo}/stargazers/history`，按**数据归属日**查、按通道轮转取号（star 区间与新仓库两个通道交替各取一条，通道内仍按 `stars_total` 降序），总量 ≤150 次/轮，`stars_today_source=star_history`；③ 都不可得记 null，单次失败仍记 `gaps`。定时任务在清晨 06:00（UTC+8）窗口取数，数据归属日为发布日前一天：`stargazers/history` 按该日历日查；本地差分以上一发布日的 `collect.json` 为基线，窗口是上次采集到本次采集（约 24 小时，起点落在清晨），与日历日归属窗口错开约 6 小时，仅在拿不到 star 历史时作近似。
- 排序与选取：在 `eligible` 中丢弃 `stars_today=null` 的候选，其余按 `stars_today` 降序取前 50；`stars_today` 全为 0 时退化为按 `stars_total` 降序；不设通道保底名额；不足 50 按实际数量输出，不足 10 在 `gaps` 说明。
- 认证（必填）：脚本从进程环境或项目根 `.env` 读取 `GITHUB_TOKEN`（兼容 `GH_TOKEN`），进程环境优先；缺失即失败，不退回未认证。`.env` 由脚本自行加载（opencode 不自动注入），`.env` 已被 git 忽略，模板见 `.env.example`。认证后配额：搜索 30 次/分、核心 5000 次/时。
- 分析阶段：为 `collect.json` 的全部条目（通常 50 条）做自由标签与 `core`/`why` 分析要点；只给 30 天外再次出现的项目写 `repeat.last_seen`，**不再剔除 30 天内项目**。**不决定入选条数、不写 `rank`/`overview`**。`core`/`why` 为分析要点，不设 100 汉字硬限。
- 整理阶段：从 analyze 候选中**定稿 10–15 条**（不足 10 按实际并在 `gaps` 说明），有权剔除但必须计入 `stats.dropped_by_organize`，`gaps` 按批次说明理由；负责 `rank`（按 `stars_today` 降序连续编号）、`overview`（自由标签合并 ≤6 组）、`core` ≤100 汉字（不计英文单词与数字）、`why` 一句评价与建议。
- 渲染：主代理按固定模板机械填充 `organize.json`，文字与数字照抄、不改写；模板见「编排协议 · 渲染模板」。标题下放质量评分摘要，每条放 star 与评分；30 天外重复只输出「🔁 重复：上次 YYYY-MM-DD」，不再输出「新进展」。
- 校验：`schemas/*.schema.json` 是字段唯一来源（spec 只解释语义），`scripts/validate.py` 用 jsonschema + 跨文件语义检查；语义阈值见 `config/validation-rules.json`（`dedupe_window_days`、`collect_min_items`、`report_min_items`、`report_max_items`、`core_max_cjk`）。默认校验当日 `work/` 产物，`--all` 校验最近一个含阶段产物的 work 日期目录（跳过只有 tokens.json 的目录），`--file` 可单独校验。
- 30 天硬校验：`validate.py` 对 analyze/organize 中的每条按 `full_name` 查窗口内历史；命中即报错，不论 `repeat` 或新进展。30 天外出现的项目必须带 `repeat.last_seen`，且 `last_seen` 等于最近一次发布日期。
- 统计透传：`collect.stats.dropped_recent_duplicates` 存在时，analyze 与 organize 的同名字段必须与上游一致；旧 collect 无 `stats` 时按 0 处理。
- 术语口径：**候选集**是搜索去重后的全部项目，**入榜集**是 `collect.json` 的 50 条，**定稿集**是 `organize.json` 的 10–15 条；三者不再混用「采集」一词。重复窗口指上述滚动 30 天。
- 校验重试：任一阶段校验失败 → 主代理把错误清单回传给同一子代理（脚本则重跑脚本），最多 3 次尝试；第 3 次仍失败即终止任务，保留产物供诊断。
- 质量评分：`.opencode/plugins/quality-score.js` 在**子代理会话**的 `write`/`edit` 命中 `organize.json` 后调用 `scripts/score.py`（Python，确定性启发式），写 `work/YYYY-MM-DD/score.json` 并把评分卡追加到工具结果尾部。opencode 插件入口须为 JS，打分逻辑全部在 Python；等级阈值、维度权重、长度档位与词表见 `config/score-rules.json`；标签维度只按标签个数计分，不依赖固定主题表。
- 质量下限：打回与 3 次终止用于守住评分下限；若需回退，删除打回环与相关步骤即可。
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

采集由 `scripts/collect.py` 执行，不设子代理与对应技能。

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

- 分析段：打标签、给 30 天外重复项标 `repeat.last_seen`、写 `core`（分析要点，承载理由与支撑事实）与 `why`（评价与建议）；不做 30 天过滤。
- 整理段：从分析结果中定稿 10–15 条、排序、压缩并润色 `core`、润色 `why`、写概览。
- 渲染段：只排版，不改字。

### 失败语义

- 完成标志：正式 JSON 完整写出并通过校验；失败时不落正式文件，已抓数据可写 `<阶段>.partial.json` 仅供人工诊断（主代理与续跑忽略）。
- 采集脚本失败：退出码非 0，stderr 给出原因；不写正式 collect.json。
- 子代理失败：返回统一失败摘要；主代理按重试规则处理。
- 校验失败：错误清单回传，最多 3 次。
- 打分打回：按条目最多 3 次；耗尽即终止，不写日报。
- 重复历史读取失败：按「无重复」保守处理并在 `gaps` 说明，不中断分析。
- 同日覆盖确认由主代理在委派整理前完成；CI 由工作流在启动 opencode 前按 `force` 判断跳过或覆盖。整理子代理直接覆盖写入。
- CI 无头运行：主代理不得向用户提问；任何需要用户决策的分支按失败处理，并保留已产出文件供 artifact 上传。

## 数据契约

字段与形状以 `schemas/` 为唯一来源；本节说明语义。JSON 为 UTF-8，`collected_at` 为本地时间（UTC+8，格式 `YYYY-MM-DD HH:mm`）。

### collect.json（采集脚本产物）

`schemas/collect.schema.json`：`date`、`collected_at`、`github[]`（collect 字段：full_name/url/description/language/stars_total/stars_today/stars_today_source/forks/created_at/pushed_at）、可选的 `stats`、`gaps[]`。

- `github` 条数 ≤50（通常 50），按 `stars_today` 降序，不含 null；不足 10 条在 `gaps` 说明。
- `stats` 可选：`{ "candidates": 993, "eligible": 949, "dropped_recent_duplicates": 44, "channels": { "star_bands": 800, "new_repos": 193 } }`；`channels` 可省略，旧产物无该字段仍有效。
- `gaps` 如实记录抓取异常、字段缺失、30 天剔除数、未纳入候选数量与 star_history 调用次数。

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
  "stats": { "github_count": 50, "dropped_recent_duplicates": 34 },
  "gaps": []
}
```

- 不含 `rank`、`overview`、`dropped_by_organize`。
- `themes` 为自由标签数组，非空字符串即可，不依赖固定主题表；建议每条 2–4 个。空数组表示「未打标签」（日报渲染为 `[其他]`）。
- `repeat`：仅 30 天外历史出现过才有，形如 `{ "last_seen": "YYYY-MM-DD" }`；`last_seen` 必须真实存在于 `daily-knowledge/` 历史，且等于最近一次发布日期。
- 30 天窗口内项目已在采集阶段剔除，分析阶段不再剔除；`dropped_recent_duplicates` 沿用 `collect.stats` 的计数（旧 collect 无 stats 时为 0）。
- 30 天外再次出现的项目照常分析并标 `repeat`，不再要求写「新进展」。

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
    "github_count": 12,
    "dropped_recent_duplicates": 34,
    "dropped_by_organize": 38
  },
  "gaps": []
}
```

- `rank` 为 `1..N` 连续整数，顺序与 `stars_today` 降序一致。
- 条目数 10–15（不足 10 按实际并在 `gaps` 说明）；`dropped_by_organize` = analyze 条目数 − organize 条目数，通常为 35–40。
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
- 「标签精度」按标签个数给分：2–4 个满分，1 个中档，≥5 个降档，0 个 0 分；具体分值与上限见 `config/score-rules.json`，不依赖固定主题表或关键词证据。

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
- 30 天窗口内的项目不得出现在 analyze/organize；`collect.json` 的 `stats` 可选，旧产物仍可通过 `--all`。
- `repeat` 不再有 `new_progress`；含该字段的旧产物属于历史数据，不自动迁移。

## 编排协议

四段由主代理（默认 build）编排；两个子代理各自只执行本阶段。

### 阶段与命令

下文 `<日期>` 均指发布日，`<数据归属日>` 指统计窗口日期：本地与手动触发两者都取今天；CI 定时任务的发布日为运行日，数据归属日为运行日前一天。

1. **采集**：`uv run python scripts/collect.py --date <日期> --gain-date <数据归属日>` → `validate.py --file work/<日期>/collect.json`。
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

> 统计窗口：昨日到今日（UTC+8）
> 质量评分：均分 X · A a / B b / C c

## 今日概览

{overview.lead}

- **{theme.name}**：{theme.note}

## GitHub 趋势

### {rank}. {full_name}

- 标签：[{theme1}] [{theme2}]
- Star：{stars_total}（今日 +{stars_today}）· 评分：{score.total} / {score.grade}
- 🔁 重复：上次 {repeat.last_seen}
- 链接：{url}
- 核心内容：{core}
- 为什么值得关注：{why}
```

- `overview.themes` 按 organize 中的顺序逐条输出；条目的 `themes` 为空数组时输出 `[其他]`。
- Star 总数用千分位；`stars_today`（数据归属日增量）照抄数值（含 0，不加千分位、不四舍五入）。
- 逐条评分只采用 `score.json.items[]` 中 `rank` 与 `full_name` 同时匹配的条目；某条匹配不到（缺项、名次或全名不符）时，该条只省略「· 评分：总分 / 等级」，Star 照常输出，其余条目与标题行不受影响。
- 标题下均分行仅在 `score.json` 存在、可解析、`valid=true` 且 `summary.average`、`summary.grades` 齐全时输出；均分照抄 `summary.average`，A/B/C 取 `summary.grades`。
- `score.json` 缺失、不可解析、`valid=false` 或 `summary` 不可用时，标题下均分行与所有逐条评分一起省略，并在汇报中说明原因。
- 无 `repeat` 时省略「🔁 重复」一行。
- 标题日期取发布日；「统计窗口」行固定为「昨日到今日（UTC+8）」，仅当数据归属日与发布日不同时输出；正文中的「今日」均指数据归属日。
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
| score.json pass=true、无发布日 daily-knowledge | 从渲染开始 |
| 发布日 daily-knowledge 已存在 | 本地：询问三选一；CI：`force=false` 跳过，`force=true` 覆盖 |

不重跑已完成阶段。

### 同日重跑（发布日 daily-knowledge 已存在）

本地由主代理提示并让用户三选一，默认第一项；CI 在启动 opencode 前判断：`force=false` 直接跳过并退出 0，`force=true` 选第一项。

1. **重新采集并覆盖**：重跑采集 → 分析 → 整理 → 渲染（发布日 work 数据被新数据覆盖，token 历史保留）。
2. **仅重写日报**：保留 work 发布日数据与评分，只重渲染 `daily-knowledge/`。
3. **取消**：什么都不做。

### 失败处理与恢复

- 子代理失败：本地由主代理向用户报告原因与建议后停止；用户说「继续知识采集」时按断点续跑。CI 直接失败、上传 artifact，不提交半成品、不重试。
- 单阶段手动触发（`@knowledge-analyze` 等）允许用于调试；前置产物缺失时该阶段应以前置缺失失败，而非自动重跑前段。
- 强制重跑某阶段：删除 `work/YYYY-MM-DD/` 下对应产物文件（或 `daily-knowledge/` 发布日文件）后重新触发；打回计次存于 `score.json`，删除它即清零。

## 测试决策

### 好测试的标准

只断言外部可观察行为：命令退出码、stdout/stderr、写出的 JSON/MD 内容，以及产物之间的一致性。测试把「日期目录里的输入」喂给脚本，断言产物是否满足契约；不 import 脚本内部函数、不断言实现细节，也不测子代理的文笔。

### 唯一的测试 seam

**脚本 CLI + 产物文件**。`collect` / `validate` / `score` 三个命令是唯一 seam，覆盖采集选取、契约校验、跨文件语义（rank 连续、core 字数、repeat 历史、剔除计数）、评分/等级/attempts 与自由标签；不新增模块级 seam。

- 真实网络不纳入测试：`tests/fixtures/` 保存 GitHub 的真实返回快照（搜索 + star 历史，注明抓取日期），测试用本地 HTTP 服务器回放，经 `KNOWLEDGE_GITHUB_API` 指向；覆盖响应形状解析、`IncompleteRead` 重试与无凭证守门。服务器需能按 star 区间与 `page` 返回不同 fixture，用于验证多查询去重与翻页；仍通过 HTTP 回放，不新增 seam。
- `work/` 与 `daily-knowledge/` 用 `KNOWLEDGE_WORK_DIR` / `KNOWLEDGE_OUTPUT_DIR` 指向临时目录，测试不读写真实目录；30 天过滤与硬校验的测试通过 `KNOWLEDGE_OUTPUT_DIR` 写入临时历史日报。
- 插件不为新行为新建 seam：`quality-score.js` 仍只转发评分；`token-stats.js` 新增的 token md 属确定性排版，由端到端验收观察（文件存在、表格数值与 `tokens.json` 一致），不做 JS 单测。
- GitHub Actions 不新建 seam：工作流语法由 GitHub 解析；在临时 `ci-smoke` 分支用真实 `workflow_dispatch` 验收（`force=true` 全流程、`force=false` 跳过、失败上传 artifact），跑通后才合并 `main`；不引入 `act` 或本地 runner 作为替身。
- 端到端仍只做人工验收：一次真实本地运行 + 一次真实 CI 运行，检查日报、评分卡、token md 与提交内容。

### 被测模块

- 采集脚本：无凭证守门（且不发请求）、star 历史解析、响应中断重试、`--date` 落盘与 `collected_at` 格式、按数据归属日新增 star 降序、30 天过滤与 `stats` 计数、多 star 区间与新仓库通道查询去重、每区间翻页、通道轮转、50 条上限、候选不足时写入 `gaps`、上一自然日 `collect.json` 的本地差分、`star_history` 150 次上限。
- 校验脚本：三份契约的正反例（未知字段、类型错误、date 与目录不一致、rank 不连续、计数不一致、repeat 历史不存在、`themes` 元素类型非法）；30 天窗口内条目硬拒（不论是否有 `repeat`）、30 天外 `repeat.last_seen` 必须等于最近发布日期、`repeat` 不再接受 `new_progress`、日报 10–15 条边界、旧 `collect.json` 无 `stats` 仍通过、`stats` 跨文件透传一致；自由标签与非固定主题被接受，空 `themes` 可接受；`--all` 跳过只有 tokens.json 的日期目录。
- 评分脚本：五维得分、A/B/C 阈值、`pass` 判定、`attempts[]` 追加、校验失败时跳过分、标签个数分档（0 / 1 / 2–4 / ≥5）。
- 不测：插件内部排版、子代理提示词与文笔、GitHub 真实网络、GitHub Actions runner。

### 先例

- `uv run python -m unittest discover -s tests -t .` 覆盖：fixture 解析、`IncompleteRead` 重试、无凭证守门、`--all` 目录选择、多区间查询去重与翻页、30 天过滤与 `stats`、10–15 条边界、旧 `collect.json` 兼容。
- 已用变异验证测试能红：去掉重试、让 star 历史解析返回 null、`--all` 只看最新目录，三种改动各自使对应测试失败。
- `validate.py` 对 `work/2026-10-09`、`work/2026-10-11` 的历史 collect.json 校验通过。
- 合成 organize.json 样本（含 A/B/C 条目、repeat、overview）跑通 validate + score，并验证第二次打分 attempt 递增。
- 自由标签用例：任意非空标签与空数组均通过校验；评分只随标签个数变化。
- 路径回归：把 `KNOWLEDGE_OUTPUT_DIR` 指向含历史日报的临时目录，repeat 历史校验与 `--all` 仍通过。
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
  - 数量与排序：GitHub 趋势 10–15 条（或 gaps 说明不足）、按 `stars_today` 降序、`rank` 连续。
  - 候选与入榜：`collect.json` 50 条（或 gaps 说明不足）、`stats.candidates - stats.dropped_recent_duplicates = stats.eligible`、`eligible >= github 条数`。
  - 标签自由：条目标签不再限定固定主题；每条建议 2–4 个；未打标签的渲染为 `[其他]`；概览分组不超过 6 组。
  - 展示齐全：每条含总 star（千分位）、数据归属日新增 star 与评分/等级；标题下含均分与 A/B/C 分布；逐条评分按 `rank` 与 `full_name` 同时匹配，单条缺失只省略该条评分，整份评分不可用才连标题行一起省略。
  - 数字可核对：条目 star 总数/数据归属日增量与 collect/organize 一致，逐条评分与 `score.json` 的 `total`/`grade` 一致，标题均分与分布与 `summary` 一致。
  - 篇幅：每条核心内容 ≤100 个汉字。
  - 去重可核查：每个 🔁 标记中的日期在 `daily-knowledge/` 历史中确实存在且为最近一次；30 天窗口内出现过的项目一条都没有出现，不论是否有新进展。
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
- 仓库改名/转移追踪：重复判定只按当前 `full_name`，不做别名映射。
- 旧产物迁移：不为含 `new_progress` 的历史 analyze/organize 提供自动迁移脚本。
- 人工白名单：不恢复固定主题表，也不维护「必采项目」名单。
- issue tracker 的完整配置（triage labels、domain docs）超出系统范围。

## 备注

- 标签由分析阶段自由生成；若将来需要引导，在技能正文里加「标签建议」，不恢复白名单。
- 30 天重复窗口是硬规则：窗口内零例外，窗口外才标 `🔁`；判断依据只看已发布日报，不看未发布的采集产物。
- 自动运行配置：在 GitHub 仓库 `Settings → Secrets and variables → Actions` 添加 `OC_GO_API_KEY`；定时为 `7 22 * * *` 与 `47 22 * * *` UTC（06:07、06:47 UTC+8，两班抢发、目标 08:00 前完成，发布当天日报，数据归属前一日）；手动 dispatch 的 `force` 用于覆盖当天。
- 定时任务的发布日通过 `KNOWLEDGE_DATE`、数据归属日通过 `KNOWLEDGE_GAIN_DATE` 贯穿工作流、采集脚本与 token 插件；手动触发也注入这两个变量，但值都取当天；本地运行不设置这两个变量，两者都取本地今天。
- 本地推送使用 `~/.ssh/git`；CI 使用自带 `GITHUB_TOKEN`，不需要 Personal Access Token。
- 本 spec 落在 local markdown tracker：`.scratch/knowledge-daily/spec.md`；tracker 配置见 `docs/agents/issue-tracker.md`。
- 术语见根目录 `GLOSSARY.md`（候选集 / 入榜集 / 定稿集 / 重复窗口）；严格去重与扩容候选池的取舍见 `docs/adr/0005-严格去重与扩容候选池.md`。
- 采集凭证的获取与配置步骤见 `AGENTS.md`「凭证」，模板见 `.env.example`。
- Python 依赖由 `uv` 管理（`pyproject.toml` + `uv.lock`），运行入口统一为 `uv run python …`。
