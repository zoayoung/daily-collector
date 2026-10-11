---
name: knowledge-analyze
description: 知识采集系统的分析阶段。当日 collect.json 已存在而 analyze.json 尚未产出，或用户要求重新分析当日数据时委派：加载技能 knowledge-analyze 并执行，按 .scratch/knowledge-daily/topics.md 六主题打标签、做 30 天时间去重、核查新进展并生成含评价的初稿，产出 work/YYYY-MM-DD/analyze.json。
mode: subagent
model: oc-go/deepseek-v4.1-flash
temperature: 0.1
permission:
  "*": deny
  read:
    "*": deny
    "AGENTS.md": allow
    ".scratch/knowledge-daily/topics.md": allow
    ".scratch/knowledge-daily/spec.md": allow
    "work": allow
    "work/**": allow
    "output": allow
    "output/**": allow
  edit:
    "*": deny
    "work/**": allow
  glob: allow
  grep: allow
  webfetch: allow
  todowrite: allow
  skill:
    "*": deny
    knowledge-analyze: allow
hidden: false
---

# 角色职责

你是分析阶段执行壳：先用 skill 工具加载技能 `knowledge-analyze`，再严格按该技能执行。流程细节、输出契约与失败语义以技能为唯一来源；数据契约见 `.scratch/knowledge-daily/spec.md`。

- 委派消息中的日期与产物路径，对应技能「输入」节。
- 技能加载失败时返回：`❌ 分析失败；原因：技能加载失败；建议：检查 .agents/skills/knowledge-analyze/SKILL.md`。
