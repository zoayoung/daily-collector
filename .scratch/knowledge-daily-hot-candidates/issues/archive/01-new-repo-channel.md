# 01: 新仓库通道进候选集

**What to build:** 采集阶段除了现有的多 star 区间搜索，再并行搜索一路「近期新建」项目（近 30 天创建、累计 star ≥ 50，按累计 star 降序，最多 2 页，不加推送时间约束）。两路候选按 `full_name` 大小写不敏感合并去重，保留首次出现的原始大小写，然后共同经过 30 天重复窗口过滤与增量计算。采集产物的统计里能分别看到两路各贡献多少候选，注释里能看到新通道的搜索失败与候选数；旧版没有通道统计的产物仍能通过契约校验。仓库条目契约不新增字段。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 新通道按「近 30 天创建 + star ≥ 50」发起搜索，`per_page=100`，最多 2 页，第一页不足 100 条不再翻页
- [x] 新通道查询不带推送时间过滤；原有 4 个 star 区间通道的行为保持不变
- [x] 两路结果合并后按 `full_name` 大小写不敏感去重，保留首次出现的原始大小写
- [x] 合并后的候选统一经过 30 天重复窗口过滤，之后才进入增量计算
- [x] 采集统计新增可选的按通道计数（区间通道、新仓库通道），数值与候选去重后的实际条数自洽
- [x] 旧产物（无通道统计字段）仍能通过契约校验，不需迁移
- [x] 注释记录新通道的候选数、搜索失败与候选总量，风格与现有注释一致
- [x] 测试通过采集 CLI 与产物验证：新通道请求被发出且条件正确、两路去重、新通道候选同样受 30 天窗口剔除、通道计数自洽、旧产物兼容

**Acceptance evidence:** 用回放服务器准备两路各自的响应，跑一次采集，产物里同时出现两路项目且计数与注释吻合；把统计字段去掉后产物仍校验通过。

## Comments

**2026-10-30 · 实现（提交 8b68acb，合并 47563c3）**

- 新通道：`created:>={发布日-30} stars:>=50`、`sort=stars`、`order=desc`、`per_page=100`、最多 2 页，首页不足 100 条不翻页；不加 `pushed` 约束。4 个 star 区间通道保持原样。
- 两路候选按 `full_name` 小写去重，保留首次出现的原始大小写；合并后统一走 30 天重复窗口与增量计算。
- `stats.channels: {star_bands, new_repos}` 由去重后的通道归属统计，`star_bands + new_repos = candidates`；`validate.py` 从 schema 派生键并校验求和。
- 注释：汇总行给出候选总量与两路拆分，新通道搜索失败单独记入 `gaps`。
- 测试（`tests/test_new_repo_channel.py` + `tests/support.py` 的通道区分）：`test_requests_recent_repos_without_pushed_filter`、`test_new_channel_fetches_second_page_only_when_first_page_is_full`、`test_merges_channels_case_insensitively_and_counts_each_channel`、`test_new_channel_candidates_are_filtered_by_duplicate_window`、`test_inconsistent_channel_stats_are_rejected`、`test_old_collect_without_channels_still_passes`。
- 验收：回放服务器分别给出两路响应后产物同时含两路项目，`stats.channels` 与注释吻合；删除 `stats.channels` 的产物仍通过校验。
