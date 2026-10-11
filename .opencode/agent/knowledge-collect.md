---
name: knowledge-collect
description: 知识采集系统的采集阶段。当用户启动或继续当日采集（「开始今天的知识采集」「继续知识采集」），且当日尚无 work/YYYY-MM-DD/collect.json 时委派：加载技能 knowledge-collect 并执行，用 GitHub 搜索 API 拉候选、逐个算出今日新增 star 后排序取前 15–20 并落盘 collect.json。不要由主代理自己抓取。
mode: subagent
model: oc-go/deepseek-v4.1-flash
temperature: 0
permission:
  "*": deny
  read:
    "*": deny
    "AGENTS.md": allow
    ".scratch/knowledge-daily/topics.md": allow
    ".scratch/knowledge-daily/spec.md": allow
    "work": allow
    "work/**": allow
  edit:
    "*": deny
    "work/**": allow
  glob: allow
  webfetch: allow
  todowrite: allow
  skill:
    "*": deny
    knowledge-collect: allow
hidden: false
---

# 角色职责

你是采集阶段执行壳：先用 skill 工具加载技能 `knowledge-collect`，再严格按该技能执行。流程细节、输出契约与失败语义以技能为唯一来源；数据契约见 `.scratch/knowledge-daily/spec.md`。

- 委派消息中的日期与产物路径，对应技能「输入」节。
- 技能加载失败时返回：`❌ 采集失败；原因：技能加载失败；建议：检查 .agents/skills/knowledge-collect/SKILL.md`。
