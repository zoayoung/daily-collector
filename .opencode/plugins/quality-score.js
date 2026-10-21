import { Plugin } from "@opencode/plugin"
import { execFile } from "node:child_process"
import path from "node:path"
import { promisify } from "node:util"

const execFileAsync = promisify(execFile)

const TARGET = /(^|[\\/])organize\.json$/i
const WRITE_TOOLS = new Set(["write", "edit"])

function extractJson(text) {
  const start = text.indexOf("{")
  const end = text.lastIndexOf("}")
  if (start === -1 || end <= start) return null
  try {
    return JSON.parse(text.slice(start, end + 1))
  } catch {
    return null
  }
}

function appendText(event, text) {
  const result = event.result
  if (result == null) return
  if (typeof result === "string") {
    event.result = `${result}\n\n${text}`
    return
  }
  if (typeof result.output === "string") {
    result.output = `${result.output}\n\n${text}`
    return
  }
  if (Array.isArray(result.content)) {
    result.content.push({ type: "text", text })
    return
  }
  result.metadata = { ...(result.metadata || {}), qualityCard: text }
}

export default Plugin.define({
  id: "knowledge-daily.quality-score",
  async setup(ctx) {
    const root = ctx.location?.directory || process.cwd()

    await ctx.tool.hook("execute.after", async (event) => {
      if (event.status && event.status !== "completed") return
      if (!WRITE_TOOLS.has(event.tool)) return
      const input = event.input || {}
      const target = input.filePath || input.path
      if (typeof target !== "string" || !TARGET.test(target)) return

      // organize.json 只由整理子代理写入，因此这里不再额外判定会话层级。
      const file = path.isAbsolute(target) ? target : path.resolve(root, target)

      try {
        const { stdout, stderr } = await execFileAsync(
          "uv",
          ["run", "python", "scripts/score.py", "--file", file, "--json"],
          { cwd: root, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
        )
        const parsed = extractJson(stdout?.toString() ?? "")
        if (!parsed?.card) {
          appendText(event, `⚠️ 质量评分未能运行：${(stderr || stdout || "").trim().slice(0, 800)}`)
          return
        }
        appendText(event, parsed.card)
      } catch (error) {
        const detail = error?.stderr?.toString() || error?.message || String(error)
        appendText(event, `⚠️ 质量评分异常：${detail.slice(0, 800)}`)
      }
    })
  },
})
