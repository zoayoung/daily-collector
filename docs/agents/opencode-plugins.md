# opencode v2 插件

本仓插件在 opencode v2.0.x 下运行。写插件前先看这几条，避免重复踩坑。

- 插件上下文**不提供** Bun 的 `$` shell；执行外部命令用 `node:child_process` 的 `execFile`（`quality-score.js` 即是）。
- `tool.execute.after(input, output)` 的 `input` 含 `tool`、`sessionID`、`args`；判断是否子代理会话用 `client.session.get({ path: { id } }).data.parentID`。
- 插件文件改动不保证热加载；验证插件行为需重启 opencode，再触发一次对应工具调用。
- 入口必须是 JS/TS，判定口径留在 Python 脚本；失败时只追加警告，不打断流程。
