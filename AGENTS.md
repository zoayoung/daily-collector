# 知识采集系统

每天产出一份中文知识日报：采集 GitHub 数据归属日的趋势项目、按项目内容自由打标签，分析、整理后按模板渲染到 `daily-knowledge/YYYY-MM-DD.md`。标签口径见 `.scratch/knowledge-daily/spec.md`。

## 工作流

1. 用户说「开始今天的知识采集」→ 一次跑完 采集 → 分析 → 整理 → 渲染 四段，产出当天日报并汇报 token。CI 定时任务以「开始知识采集；发布日 YYYY-MM-DD；数据归属 YYYY-MM-DD」触发，以消息里的两个日期为准。
2. 中途失败 → 用户说「继续知识采集」→ 从断点续跑，不重跑已完成阶段。
3. 发布日日报已存在 → 先提示，三选一：重新采集并覆盖（默认）/ 仅重写日报 / 取消；「仅重写」保留 work 发布日数据与评分。
4. 发布日按本地日期（UTC+8）；CI 定时任务的数据归属为发布日前一天，消息或 `KNOWLEDGE_GAIN_DATE` 给出数据归属时以它为准。
5. 需强制重跑某阶段 → 删除 `work/YYYY-MM-DD/` 对应产物（或 `daily-knowledge/` 发布日文件）后重新触发；删除 `score.json` 即清零打回计次。
6. 校验失败 → 回传错误重试，同阶段 3 次仍失败即终止；条目评分 <60 → 打回重做，同一条目 3 次仍 <60 即终止且不发日报。

编排细则（委派顺序、校验环/打分环、断点表、覆盖与恢复、渲染模板）见 `.scratch/knowledge-daily/spec.md` 的「编排协议」节。执行任一阶段前，先读该 spec——采集口径、打标签口径、去重规则、契约与产出结构的细则都在那里。

## 自动运行

GitHub Actions 每个自然日 08:00（UTC+8）无头运行同一套流程，发布当天日报、数据归属前一日，工作流见 `.github/workflows/daily-knowledge.yml`；触发、参数、幂等、失败与冒烟口径见 spec 的「自动运行」「CI 参数/凭证/幂等/失败/并发/冒烟」节。

- 手动触发支持 `force` 覆盖；发布日日报已存在时的跳过与覆盖口径见 spec 的「CI 幂等」。
- 成功后只提交 `daily-knowledge/` 与发布日 `work/YYYY-MM-DD/collect.json`；其余中间产物不入库。
- 失败不提交半成品、不自动重试，只上传 `work/<发布日>/` artifact。

## 约束

- 默认只读：未经用户明确要求，不修改项目中的任何文件、不开始实施、不提交或推送。用户只要求改文档时，只改指定文档。
- 采集由 Python 脚本（`scripts/collect.py`）完成；契约校验与质量评分为 Python（`scripts/validate.py`、`scripts/score.py`）；其余阶段零脚本。
- 字段与形状以 `schemas/` 为唯一来源；评分词表在 `config/score-rules.json`，校验语义阈值在 `config/validation-rules.json`；三者都不在技能里复述。
- 子代理只有两个：`knowledge-analyze`（分析）与 `knowledge-organize`（整理）；采集不再是子代理。
- 技能/agent/文档的写法规范（供 `/code-review` 标准轴）见 `docs/agents/CODING_STANDARDS.md`。
- 产出用中文；项目名/标题保留原文。
- opencode 自身的 agent、插件与脚本配置不算「流程复述」，在子代理设计阶段确定。
- 除配置文件外，其余文件均使用中文。

## 数据

- `work/YYYY-MM-DD/`：collect / analyze / organize / score / tokens 等中间 json，本地保留（.gitignore）；版本控制只放行每日 `collect.json`
- `daily-knowledge/YYYY-MM-DD.md`：知识日报；`daily-knowledge/tokens/YYYY-MM-DD.md`：token 报告；均纳入版本控制
- `.scratch/knowledge-daily/requirements/`：原始需求按日期归档（只读）；当前行为只看 spec

## 脚本与插件

- `uv run python scripts/collect.py|validate.py|score.py`：采集、校验、评分；依赖由 `uv` 管理。
- `.opencode/plugins/quality-score.js`：写 `organize.json` 后自动校验并打分。
- 开发检查：首次执行 `git config core.hooksPath .githooks`，之后 pre-commit 会跑 ruff、compileall、CLI 回归测试（`uv run python -m unittest discover -s tests -t .`）、`node --check`、JSON 解析与插件 `$` 扫描。
- `.opencode/plugins/token-stats.js`：聚合每次运行的 token 消耗到 `work/YYYY-MM-DD/tokens.json`，并生成人可读的 `daily-knowledge/tokens/YYYY-MM-DD.md`（格式见 spec「tokens.json（用量产物）」节）；文件名取 `KNOWLEDGE_DATE`（发布日），数据归属日取 `KNOWLEDGE_GAIN_DATE` 且与发布日不同时在正文标注统计窗口，未设置时都取本地今天。

## 凭证

采集必须使用 `GITHUB_TOKEN`（缺失即失败，不退回未认证）。

- 配置：复制 `.env.example` 为项目根 `.env`，填 `GITHUB_TOKEN=...`；也可直接设进程环境变量。进程环境优先于 `.env`（`.env` 已被 git 忽略）。
- 获取：GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → `Generate new token`；Repository access 选 `Public repositories (read-only)`，无需额外权限。classic token 不勾任何 scope 也可。
- 认证后配额：搜索 30 次/分、核心 5000 次/时。
- CI：模型密钥只放仓库 Secret `OC_GO_API_KEY`（`opencode.json` 以 `{env:OC_GO_API_KEY}` 引用）；采集与回写使用 Actions 自带 `GITHUB_TOKEN`，不额外配置 Personal Access Token。

## Agent skills

### Issue tracker

议题与规格以 markdown 文件存放在 `.scratch/<feature-slug>/`（本地 Markdown 追踪器）。见 `docs/agents/issue-tracker.md`。

### Triage labels

分诊使用五个标准角色，标签串与角色同名。见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：根目录 `GLOSSARY.md` + `docs/adr/`。见 `docs/agents/domain.md`。
