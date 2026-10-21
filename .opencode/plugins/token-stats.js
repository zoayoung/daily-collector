import fs from "node:fs/promises"
import path from "node:path"

const OFFSET_MS = 8 * 60 * 60 * 1000

function localDate(timestamp) {
  return new Date(timestamp + OFFSET_MS).toISOString().slice(0, 10)
}

function localStamp(timestamp) {
  const date = new Date(timestamp + OFFSET_MS)
  const pad = (value) => String(value).padStart(2, "0")
  return (
    `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ` +
    `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`
  )
}

function emptyBucket() {
  return {
    messages: 0,
    input: 0,
    output: 0,
    reasoning: 0,
    cache_read: 0,
    cache_write: 0,
    cost: 0,
  }
}

function addBucket(target, message) {
  target.messages += 1
  target.input += message.input
  target.output += message.output
  target.reasoning += message.reasoning
  target.cache_read += message.cache_read
  target.cache_write += message.cache_write
  target.cost += message.cost
}

const AGENT_ORDER = ["build", "knowledge-analyze", "knowledge-organize"]
const BUCKET_KEYS = ["messages", "input", "output", "cache_read", "cache_write", "reasoning", "cost"]
// 子会话向上找根会话的最大层数，防止异常数据造成无限循环
const MAX_SESSION_DEPTH = 10

function orderedAgents(agents) {
  const rest = Object.keys(agents)
    .filter((name) => !AGENT_ORDER.includes(name))
    .sort((a, b) => a.localeCompare(b))
  return [...AGENT_ORDER.filter((name) => Object.hasOwn(agents, name)), ...rest]
}

function bucketCells(bucket) {
  return BUCKET_KEYS.map((key) => (bucket?.[key] == null ? "" : String(bucket[key])))
}

function tableRow(bucket, label) {
  const cells = bucketCells(bucket).join(" | ")
  return label == null ? `| ${cells} |` : `| ${label} | ${cells} |`
}

function endClock(startedAt, updatedAt) {
  const sameDay = String(updatedAt).startsWith(`${String(startedAt).slice(0, 10)} `)
  return sameDay ? String(updatedAt).slice(11) : String(updatedAt)
}

function sumRuns(runs) {
  const total = Object.fromEntries(BUCKET_KEYS.map((key) => [key, 0]))
  for (const run of runs) {
    for (const key of BUCKET_KEYS) total[key] += Number(run.total?.[key] || 0)
  }
  return total
}

function renderReport(date, runs) {
  const sections = runs.map((run, index) => {
    const rows = orderedAgents(run.agents).map((agent) => tableRow(run.agents[agent], agent))
    if (run.total) rows.push(tableRow(run.total, "合计"))
    return [
      `## Run ${index + 1} · ${run.started_at} – ${endClock(run.started_at, run.updated_at)}`,
      "",
      "| 代理 | 消息数 | input | output | cache 读 | cache 写 | reasoning | cost(USD) |",
      "| --- | --- | --- | --- | --- | --- | --- | --- |",
      ...rows,
    ].join("\n")
  })

  const daily = [
    "## 当日合计",
    "",
    "| 消息数 | input | output | cache 读 | cache 写 | reasoning | cost(USD) |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    tableRow(sumRuns(runs)),
  ].join("\n")

  return [`# Token 统计 · ${date}`, ...sections, daily].join("\n\n") + "\n"
}

async function writeReport(root, date, runs) {
  if (!Array.isArray(runs) || runs.length === 0) return
  const file = path.join(root, "daily-knowledge", "tokens", `${date}.md`)
  const temp = `${file}.${process.pid}.tmp`
  await fs.mkdir(path.dirname(file), { recursive: true })
  await fs.writeFile(temp, renderReport(date, runs), "utf8")
  await fs.rename(temp, file)
}

export const TokenStats = async ({ client, directory, worktree }) => {
  const root = worktree || directory
  const sessionRoot = new Map()
  const messages = new Map()
  let timer = null

  async function resolveRoot(sessionID) {
    if (!sessionID) return "unknown"
    if (sessionRoot.has(sessionID)) return sessionRoot.get(sessionID)
    sessionRoot.set(sessionID, sessionID)
    let current = sessionID
    for (let depth = 0; depth < MAX_SESSION_DEPTH; depth += 1) {
      let parent
      try {
        const response = await client.session.get({ path: { id: current } })
        parent = response?.data?.parentID ?? response?.parentID
      } catch {
        break
      }
      if (!parent) break
      current = parent
    }
    sessionRoot.set(sessionID, current)
    return current
  }

  // opencode 的消息信息在不同版本里用 mode 或 agent 表示代理名，按此顺序取第一个有值的
  function agentName(info) {
    return info.mode || info.agent || "unknown"
  }

  function record(info) {
    if (!info || info.role !== "assistant" || info.time?.completed == null) return
    const tokens = info.tokens || {}
    messages.set(info.id, {
      sessionID: info.sessionID,
      agent: agentName(info),
      created: info.time?.created ?? Date.now(),
      input: tokens.input || 0,
      output: tokens.output || 0,
      reasoning: tokens.reasoning || 0,
      cache_read: tokens.cache?.read || 0,
      cache_write: tokens.cache?.write || 0,
      cost: info.cost || 0,
    })
  }

  function scheduleFlush() {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      flush().catch(() => {})
    }, 400)
  }

  async function flush() {
    if (messages.size === 0) return

    const grouped = new Map()
    for (const message of messages.values()) {
      const rootSession = await resolveRoot(message.sessionID)
      let run = grouped.get(rootSession)
      if (!run) {
        run = {
          root_session: rootSession,
          started_at: localStamp(message.created),
          start_ms: message.created,
          agents: {},
          total: emptyBucket(),
        }
        grouped.set(rootSession, run)
      }
      run.start_ms = Math.min(run.start_ms, message.created)
      run.started_at = localStamp(run.start_ms)
      run.agents[message.agent] = run.agents[message.agent] || emptyBucket()
      addBucket(run.agents[message.agent], message)
      addBucket(run.total, message)
    }

    const day = localDate(Date.now())
    const file = path.join(root, "work", day, "tokens.json")
    let existing = { date: day, runs: [] }
    try {
      existing = JSON.parse(await fs.readFile(file, "utf8"))
    } catch (error) {
      // 文件不存在时正常新建；存在却读不出或解析失败时丢弃本轮统计，
      // 不覆盖 tokens.json、不生成 md，避免破坏历史数据
      if (error?.code !== "ENOENT") return
    }
    if (!existing || typeof existing !== "object") return
    if (!Array.isArray(existing.runs)) existing.runs = []

    for (const run of grouped.values()) {
      delete run.start_ms
      run.updated_at = localStamp(Date.now())
      const index = existing.runs.findIndex((item) => item.root_session === run.root_session)
      if (index === -1) existing.runs.push(run)
      else existing.runs[index] = run
    }

    existing.date = day
    existing.updated_at = localStamp(Date.now())
    existing.runs.sort((a, b) => String(a.started_at).localeCompare(String(b.started_at)))

    await fs.mkdir(path.dirname(file), { recursive: true })
    const temp = `${file}.${process.pid}.tmp`
    await fs.writeFile(temp, `${JSON.stringify(existing, null, 2)}\n`, "utf8")
    await fs.rename(temp, file)

    await writeReport(root, day, existing.runs)
  }

  return {
    event: async ({ event }) => {
      if (event.type === "message.updated") {
        record(event.properties?.info)
        scheduleFlush()
        return
      }
      if (event.type === "session.idle") {
        await flush().catch(() => {})
      }
    },
    dispose: async () => {
      if (timer) clearTimeout(timer)
      await flush().catch(() => {})
    },
  }
}
