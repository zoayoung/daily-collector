# 知识采集系统

每天产出一份中文知识日报：采集 GitHub 当日趋势项目、按关注主题打标签，分析后写入 `output/YYYY-MM-DD.md`。关注主题定义见 `.scratch/knowledge-daily/topics.md`。

## 工作流

1. 用户说「开始今天的知识采集」→ 一次跑完 采集 → 分析 → 输出 三段，产出当天日报。
2. 中途失败 → 用户说「继续知识采集」→ 从断点续跑，不重跑已完成阶段。
3. 当天日报已存在 → 先提示，三选一：重新采集并覆盖（默认）/ 仅重写日报 / 取消；「仅重写」保留 work 当天数据。
4. 日期按本地日期（UTC+8）归属。
5. 需强制重跑某阶段 → 删除 `work/YYYY-MM-DD/` 对应产物（或 `output/` 当日文件）后重新触发。

编排细则（委派顺序、断点表、覆盖与恢复）见 `.scratch/knowledge-daily/spec.md` 的「编排协议」节。执行任一阶段前，先读该 spec——采集源、打标签口径、去重规则、产出结构的细则都在那里。

## 约束

- 零脚本：采集、分析、写作全部由子代理用内置 web 工具完成；配置一律用手工维护的 md。
- 技能/agent/文档的写法规范（供 `/code-review` 标准轴）见 `docs/agents/CODING_STANDARDS.md`。
- 产出用中文；项目名/标题保留原文。
- opencode 自身的 agent 配置不属于「代码」，在子代理设计阶段确定。
- 除配置文件外，其余均文件均使用中文

## 数据

- `work/YYYY-MM-DD/`：中间 json，本地保留（.gitignore）
- `output/YYYY-MM-DD.md`：知识日报，本地保留（.gitignore）

## Agent skills

### Issue tracker

议题与规格以 markdown 文件存放在 `.scratch/<feature-slug>/`（本地 Markdown 追踪器）。见 `docs/agents/issue-tracker.md`。

### Triage labels

分诊使用五个标准角色，标签串与角色同名。见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：根目录 `GLOSSARY.md` + `docs/adr/`。见 `docs/agents/domain.md`。
