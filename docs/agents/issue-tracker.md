# 议题追踪器：本地 Markdown

本仓库的议题（issue）与规格（spec）以 markdown 文件形式存放于 `.scratch/`。

## 约定

- 每个功能一个目录：`.scratch/<feature-slug>/`
- 规格文件为 `.scratch/<feature-slug>/spec.md`
- 实现类议题每张工单一文件，位于 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 开始编号，绝不合并为单个工单文件
- 分诊（triage）状态记录在每个议题文件顶部附近的 `Status:` 行（角色字符串见 `triage-labels.md`）
- 评论与对话历史追加到文件底部，置于 `## Comments` 标题之下

## 当某个技能说「发布到议题追踪器」时

在 `.scratch/<feature-slug>/` 下新建一个文件（如目录不存在则一并创建）。

## 当某个技能说「获取相关工单」时

读取所引用路径处的文件。用户通常会直接给出路径或工单编号。

## Wayfinding 操作

由 `/wayfinder` 使用。**地图（map）**是一个文件，每张工单对应一个**子（child）**文件。

- **地图**：`.scratch/<effort>/map.md`（其正文为 Notes / Decisions-so-far / Fog）。
- **子工单**：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 开始编号，正文中写明问题。`Type:` 行记录工单类型（`research`/`prototype`/`grilling`/`task`）；`Status:` 行记录 `claimed`/`resolved`。
- **阻塞**：顶部附近有一行 `Blocked by: NN, NN`。当某工单所列出的每个文件都处于 `resolved` 状态时，该工单即解除阻塞。
- **前沿（frontier）**：扫描 `.scratch/<effort>/issues/`，找出处于 open、未阻塞且未认领状态的文件；编号最小者优先。
- **认领（claim）**：设定 `Status: claimed` 并在开展任何工作之前保存。
- **解决（resolve）**：在 `## Answer` 标题下追加答案，设定 `Status: resolved`，随后在 `map.md` 的 Decisions-so-far 中追加一个上下文指针（要点 + 链接）。
