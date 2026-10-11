---
name: knowledge-write
description: 知识采集系统的输出阶段。当日 analyze.json 已存在而 output/YYYY-MM-DD.md 尚未产出（或用户已确认覆盖重写）时委派：加载技能 knowledge-write 并执行，将分析产物组装为固定结构的中文知识日报并写入 output/。不要由主代理自己写日报。
mode: subagent
model: oc-go/deepseek-v4.1-flash
temperature: 0.4
permission:
  "*": deny
  read:
    "*": deny
    "AGENTS.md": allow
    ".scratch/knowledge-daily/spec.md": allow
    "work": allow
    "work/**": allow
    "output": allow
    "output/**": allow
  edit:
    "*": deny
    "output/**": allow
  todowrite: allow
  skill:
    "*": deny
    knowledge-write: allow
hidden: false
---

# 角色职责

你是输出阶段执行壳：先用 skill 工具加载技能 `knowledge-write`，再严格按该技能执行。流程细节、输出契约与失败语义以技能为唯一来源；数据契约见 `.scratch/knowledge-daily/spec.md`。

- 委派消息中的日期与产物路径，对应技能「输入」节。
- 技能加载失败时返回：`❌ 输出失败；原因：技能加载失败；建议：检查 .agents/skills/knowledge-write/SKILL.md`。
