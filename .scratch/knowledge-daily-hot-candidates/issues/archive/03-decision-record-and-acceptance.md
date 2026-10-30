# 03: 决策记录与真实数据验收

**What to build:** 把这次候选池扩容的取舍沉淀为架构决策记录（编号顺延），说明为什么单纯扩 star 区间仍会漏掉新建爆款、为什么不用事件流或趋势页面、以及它与既有「多 star 区间扩容」决策的关系。同时把工作流规格中的采集口径改写为与实现一致，并用真实数据对既有日期做一次只读采集对比，用证据确认以前漏掉的热门项目现在能入榜。

**Blocked by:** 01: 新仓库通道进候选集, 02: 增量预算轮转

**Status:** done

- [x] 新增架构决策记录，编号顺延，内容覆盖：问题、替代方案（事件流、趋势页面、创建时间单约束）、选择理由、与既有扩容决策的关系
- [x] 工作流规格中的候选池、过滤与计数、新增 star 口径、排序与选取四段与实现一致
- [x] 领域词汇表不新增术语
- [x] 对既有日期做只读采集对比：新增候选中至少 3 条当日增量为正且在旧规则下未入榜
- [x] 采集统计自洽，注释无自相矛盾
- [x] 全量单元测试、静态检查与编译检查通过

**Acceptance evidence:** 提交前的检查命令全部通过；对比记录（哪几条是新通道捞回的、增量多少）附在本工单 Comments 下。

## Comments

**2026-10-30 · 03 实现子代理**

- ADR：新增 `docs/adr/0008-新增新仓库通道并按通道轮转增量预算.md`，说明与 ADR-0005 的关系（0005 管区间覆盖与去重，0008 补时间维度通道并把手次上限 100→150），不设通道保底名额。
- 工作流 spec：`.scratch/knowledge-daily/spec.md` 已改写候选池口径、采集过滤与计数、新增 star 口径、排序与选取四段，并同步 `stats` 示例、`Updated` 日期与相关用户故事中的 100→150、候选规模约 800→1000；GLOSSARY.md 未新增术语。
- 检查：`ruff check scripts tests` 通过；`python -m compileall -q scripts` 通过；`python -m unittest discover -s tests -t .` 通过，共 84 个测试。

**真实数据只读对比（dry-run，不写仓库内产物）**

- 日期：`--date 2026-10-23 --gain-date 2026-10-22`（首组日期即满足 3 条，未换日期）。
- 产物：`C:\Users\z4960\AppData\Local\Temp\opencode\hot-notes\dry-run-2026-10-23.json`（UTF-16，PowerShell 重定向）；与主仓库 `work/2026-10-23/collect.json` 对比。
- `stats`：`{"candidates": 993, "eligible": 949, "dropped_recent_duplicates": 44, "channels": {"star_bands": 800, "new_repos": 193}}`，800 + 193 = 993，与候选数自洽。
- gaps 关键行：
  - `候选 993 个，30 天窗口剔除 44 个，入榜 50 个`
  - `新仓库通道贡献 193 条候选`
  - `star_history 调用 150 次（上限 150），失败 4 次`
  - `历史增量预算耗尽（上限 150 次），761 个候选未计算增量`
  - 4 次失败：`unclebob/ub-mode`、`anhao/ai-pose-gallery-zh`、`interplains/Zero-Breach-Toolkit`、`designfuchen/word-atlas`（均记 null，未伪造数据）。
- 新 dry-run 中 `stars_today > 0` 且不在旧入榜集的条目共 **26 条**；其中 `created_at >= 2026-09-23`（新仓库通道 30 天窗口）的有 **17 条**。按增量降序前 10：

| full_name | stars_today | stars_total | created_at | 创建窗口 |
| --- | ---: | ---: | --- | --- |
| Gathin23/cleanyourtv | +4607 | 46177 | 2026-10-17 | 新仓库 |
| Ebony-Vinyl/dsh-our-free-model | +2718 | 52261 | 2026-09-24 | 新仓库 |
| deepseek-ai/DeepInfer | +1599 | 24429 | 2026-10-16 | 新仓库 |
| debpalash/VoiceStudio | +1288 | 95116 | 2026-04-09 | 区间 |
| KnifeLemon/Filee | +1033 | 18182 | 2026-09-29 | 新仓库 |
| pengchujin/aerial-tv | +887 | 7971 | 2026-10-20 | 新仓库 |
| seedds/nxnative | +851 | 10022 | 2026-10-13 | 新仓库 |
| 2dust/v2rayN | +772 | 119530 | 2019-07-30 | 区间 |
| yetone/magpie | +751 | 26041 | 2026-09-23 | 新仓库 |
| google-research/harness2 | +736 | 21440 | 2026-10-06 | 新仓库 |

- 口径说明：仓库条目（`github[]`）不写通道标记，通道来源仅见 `stats.channels` 汇总；表中「新仓库」按 `created_at` 是否落在新通道窗口判定；两路重叠时脚本保留 star 区间通道的首次出现，无法从产物反推精确来源。区间通道条目（如 `debpalash/VoiceStudio`、`2dust/v2rayN`）此前未入榜，来自预算由 100 提到 150 并轮转后不再被队尾挤掉。

**2026-10-30 · 归档说明**

- 代码审查修复（提交 d4bd9bc，合并 51f51fd）修正了预算耗尽文案的「未尝试」计数口径；全量测试增至 85 个。
- 复审修复：恢复 `gaps` 中独立的「新仓库通道贡献 N 条候选」行（汇总行继续给出两路拆分），与验收证据一致；`stats.channels` 的写法统一为「仅汇总计数写入产物，仓库条目不写通道标记」；补齐新通道首页不足 100 条不翻页的负向用例；全量测试 86 个。
- 顺带维护（本工单范围外的正确改动，保留并在此备案）：ADR-0006 增加「被 ADR-0007 取代」注记；主 spec 除四段外同步了用户故事与「被测模块」清单中的 100→150、候选规模约 800→1000。
- 验收证据入库：dry-run 原始产物见 `.scratch/knowledge-daily-hot-candidates/acceptance/collect-2026-10-23.json`（`stats.channels` 800/193、gaps 含独立贡献行），复现命令 `uv run python scripts/collect.py --date 2026-10-23 --gain-date 2026-10-22 --dry-run`。
- 交付分支：`feat/hot-candidates`。
