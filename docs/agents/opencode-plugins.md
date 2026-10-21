# opencode v2 插件

本仓插件在 opencode v2.0.x 下运行。写插件前先看这几条，避免重复踩坑。

- 插件默认导出 `Plugin.define({ id, setup(ctx) })`；V1 的具名导出函数不会被加载。
- 插件上下文**不提供** Bun 的 `$` shell；执行外部命令用 `node:child_process` 的 `execFile`（`quality-score.js` 即是）。
- 工具钩子用 `ctx.tool.hook("execute.after", event => …)`；事件字段是 `event.tool`、`event.input`、`event.status`、`event.result`，不再是 V1 的 `(input, output)` 两参数。
- 运行事件用 `ctx.event.subscribe({ signal })` 订阅；token 统计应读 `session.created`、`session.step.ended` 与 `session.usage.updated`，V1 的 `message.updated` 在 V2 不存在。
- 插件文件改动不保证热加载；验证插件行为需重启 opencode，再触发一次对应工具调用或会话。
- 入口必须是 JS/TS，判定口径留在 Python 脚本；失败时只追加警告，不打断流程。
