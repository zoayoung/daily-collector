# 分诊标签

各技能以五个标准分诊角色来表述。本文件把这些角色映射到本仓库追踪器实际使用的标签串。

| 技能中的角色 | 本仓库的标签 | 含义 |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | 维护者需要评估此议题 |
| `needs-info` | `needs-info` | 等待报告者补充信息 |
| `ready-for-agent` | `ready-for-agent` | 已充分定义，可交给 AFK 代理 |
| `ready-for-human` | `ready-for-human` | 需要人工实现 |
| `wontfix` | `wontfix` | 不予处理 |
| 无（终态） | `done` | 已完成并归档 |

本仓库使用本地 Markdown 追踪器，分诊状态以议题文件顶部的 `Status:` 行记录（取值即上表「本仓库的标签」列）。当某个技能提到某个角色（例如「应用 AFK-ready 分诊标签」），请使用本表中对应的标签串。工单完成并移入 `issues/archive/` 时，`Status:` 改为 `done`。

若要改用其它词汇，编辑「本仓库的标签」列即可。
