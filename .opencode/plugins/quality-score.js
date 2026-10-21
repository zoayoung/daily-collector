import path from "node:path"

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

export const QualityScore = async ({ $, directory, worktree }) => {
  const root = worktree || directory

  return {
    "tool.execute.after": async (input, output) => {
      if (!WRITE_TOOLS.has(input.tool)) return
      const target = input.args?.filePath || input.args?.path
      if (typeof target !== "string" || !TARGET.test(target)) return

      const file = path.isAbsolute(target) ? target : path.resolve(root, target)

      try {
        const result = await $`uv run python scripts/score.py --file ${file} --json`
          .cwd(root)
          .quiet()
          .nothrow()
        const stdout = result.stdout?.toString() ?? ""
        const parsed = extractJson(stdout)
        if (!parsed?.card) {
          const stderr = result.stderr?.toString() ?? ""
          output.output = `${output.output}\n\n⚠️ 质量评分未能运行：${(stderr || stdout).trim().slice(0, 800)}`
          return
        }
        output.output = `${output.output}\n\n${parsed.card}`
      } catch (error) {
        output.output = `${output.output}\n\n⚠️ 质量评分异常：${String(error).slice(0, 800)}`
      }
    },
  }
}
