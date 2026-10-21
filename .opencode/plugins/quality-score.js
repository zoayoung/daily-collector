import { execFile } from "node:child_process"
import path from "node:path"
import { promisify } from "node:util"

const execFileAsync = promisify(execFile)

const TARGET = /(^|[\\/])organize\.json$/i
const WRITE_TOOLS = new Set(["write", "edit"])

async function isSubagentSession(client, sessionID) {
  if (!sessionID) return false
  try {
    const response = await client.session.get({ path: { id: sessionID } })
    const session = response?.data ?? response
    return Boolean(session?.parentID)
  } catch {
    return true
  }
}

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

export const QualityScore = async ({ client, directory, worktree }) => {
  const root = worktree || directory

  return {
    "tool.execute.after": async (input, output) => {
      if (!WRITE_TOOLS.has(input.tool)) return
      const target = input.args?.filePath || input.args?.path
      if (typeof target !== "string" || !TARGET.test(target)) return
      if (!(await isSubagentSession(client, input.sessionID))) return

      const file = path.isAbsolute(target) ? target : path.resolve(root, target)

      try {
        const { stdout, stderr } = await execFileAsync(
          "uv",
          ["run", "python", "scripts/score.py", "--file", file, "--json"],
          { cwd: root, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
        )
        const parsed = extractJson(stdout?.toString() ?? "")
        if (!parsed?.card) {
          output.output = `${output.output}\n\n⚠️ 质量评分未能运行：${(stderr || stdout || "").trim().slice(0, 800)}`
          return
        }
        output.output = `${output.output}\n\n${parsed.card}`
      } catch (error) {
        const detail = error?.stderr?.toString() || error?.message || String(error)
        output.output = `${output.output}\n\n⚠️ 质量评分异常：${detail.slice(0, 800)}`
      }
    },
  }
}
