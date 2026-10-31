# 05: 层内同分的次级排序口径

**What to build:** 层内主键相同时的次级排序成为正式口径，而不是只存在于采集脚本里的隐式行为。规格的排序段落明确：层内先按数据归属日新增 star 降序，相同时按累计 star 降序；全零兜底保持不变。采集、校验与测试对同分次序的理解一致，日报顺序可复现。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 工作流 spec 的「排序与选取」写明层内同分时按累计 star 降序
- [ ] 采集产物在层内同分时按累计 star 降序，测试锁定该次序
- [ ] 校验脚本的分层降序校验接受同分次序，不误报
- [ ] 全零时层内按累计 star 降序的既有行为保持不变

**Acceptance evidence:** 构造两条同一层、同一 `stars_today`、不同 `stars_total` 的候选，采集产物中累计 star 高者在前；把采集产物交给校验脚本通过。

## Comments
