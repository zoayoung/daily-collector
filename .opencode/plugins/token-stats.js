import { Plugin } from "@opencode/plugin"
import fs from "node:fs/promises"
import path from "node:path"

const OFFSET_MS = 8 * 60 * 60 * 1000
const AGENT_ORDER = ["build", "knowledge-analyze", "knowledge-organize"]
const BUCKET_KEYS = ["messages", "input", "output", "cache_read", "cache_write", "reasoning", "cost"]
const MAX_SESSION_DEPTH = 10

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

function tokenFields(tokens) {
  return {
    input: tokens?.input || 0,
    output: tokens?.output || 0,
    reasoning: tokens?.reasoning || 0,
    cache_read: tokens?.cache?.read || 0,
    cache_write: tokens?.cache?.write || 0,
  }
}

export default Plugin.define({
  id: "knowledge-daily.token-stats",
  async setup(ctx) {
    const root = ctx.location?.directory || process.cwd()
    const controller = new AbortController()
    const sessions = new Map()
    const steps = new Map()
    const usage = new Map()
    const resolvedRoots = new Map()

    async function resolveRoot(sessionID) {
      if (!sessionID) return "unknown"
      if (resolvedRoots.has(sessionID)) return resolvedRoots.get(sessionID)
      let current = sessionID
      let parent = sessions.get(current)?.parentID
      for (let depth = 0; depth < MAX_SESSION_DEPTH && !parent; depth += 1) {
        try {
          const session = await ctx.session.get({ sessionID: current })
          parent = session?.parentID ?? session?.parent?.id
        } catch {
          break
        }
        if (!parent) break
        current = parent
      }
      const rootSession = parent || current
      resolvedRoots.set(sessionID, rootSession)
      return rootSession
    }

    function trackSession(data, created) {
      if (!data?.sessionID) return
      const previous = sessions.get(data.sessionID) || {}
      sessions.set(data.sessionID, {
        ...previous,
        agent: data.agent || previous.agent || "unknown",
        parentID: data.parentID ?? previous.parentID,
        created: previous.created ?? created ?? Date.now(),
      })
    }

    function trackStep(data, created) {
      if (!data?.sessionID) return
      const set = steps.get(data.sessionID) || new Set()
      if (data.assistantMessageID) set.add(data.assistantMessageID)
      else set.add(`${data.sessionID}-${created ?? Date.now()}`)
      steps.set(data.sessionID, set)
      if (!sessions.has(data.sessionID)) {
        sessions.set(data.sessionID, { agent: "unknown", created: created ?? Date.now() })
      }
    }

    function trackUsage(data) {
      if (!data?.sessionID) return
      usage.set(data.sessionID, {
        cost: data.cost || 0,
        ...tokenFields(data.tokens),
      })
    }

    // 根会话可能在插件订阅事件之前就已创建，这里补查一次会话信息拿代理名与父会话
    async function ensureAgent(sessionID) {
      const session = sessions.get(sessionID)
      if (session?.agent && session.agent !== "unknown") return
      try {
        const info = await ctx.session.get({ sessionID })
        sessions.set(sessionID, {
          ...session,
          agent: info?.agent || session?.agent || "unknown",
          parentID: info?.parentID ?? session?.parentID,
          created: session?.created ?? Date.now(),
        })
      } catch {
        if (!session) sessions.set(sessionID, { agent: "unknown", created: Date.now() })
      }
    }

    async function flush() {
      if (sessions.size === 0) return
      for (const sessionID of sessions.keys()) {
        await ensureAgent(sessionID)
      }

      const grouped = new Map()
      for (const [sessionID, session] of sessions) {
        const rootSession = await resolveRoot(sessionID)
        let run = grouped.get(rootSession)
        if (!run) {
          run = {
            root_session: rootSession,
            started_at: localStamp(session.created),
            start_ms: session.created,
            agents: {},
            total: emptyBucket(),
          }
          grouped.set(rootSession, run)
        }
        run.start_ms = Math.min(run.start_ms, session.created)
        run.started_at = localStamp(run.start_ms)

        const agent = session.agent || "unknown"
        const bucket = run.agents[agent] || emptyBucket()
        const counts = steps.get(sessionID)
        bucket.messages += counts ? counts.size : 0
        const totals = usage.get(sessionID)
        if (totals) {
          bucket.input += totals.input
          bucket.output += totals.output
          bucket.reasoning += totals.reasoning
          bucket.cache_read += totals.cache_read
          bucket.cache_write += totals.cache_write
          bucket.cost += totals.cost
        }
        run.agents[agent] = bucket
      }

      for (const run of grouped.values()) {
        run.total = emptyBucket()
        for (const bucket of Object.values(run.agents)) {
          for (const key of BUCKET_KEYS) run.total[key] += bucket[key]
        }
      }

      const day = localDate(Date.now())
      const file = path.join(root, "work", day, "tokens.json")
      let existing = { date: day, runs: [] }
      try {
        existing = JSON.parse(await fs.readFile(file, "utf8"))
        if (!Array.isArray(existing.runs)) existing.runs = []
      } catch (error) {
        if (error?.code !== "ENOENT") return
      }

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

    void (async () => {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        if (event.type === "session.created") {
          trackSession(event.data, event.created)
        } else if (event.type === "session.step.ended") {
          trackStep(event.data, event.created)
        } else if (event.type === "session.usage.updated") {
          trackUsage(event.data)
        } else if (event.type === "session.execution.succeeded") {
          await flush()
        } else if (event.type === "session.idle") {
          await flush()
        }
      }
    })().catch(() => {})

    return async () => {
      controller.abort()
      await flush().catch(() => {})
    }
  },
})
