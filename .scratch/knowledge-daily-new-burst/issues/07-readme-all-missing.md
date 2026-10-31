# 07: README 全部缺失时的失败语义

**What to build:** 按规格，入榜不足按实际数量输出并在 `gaps` 说明；所有候选都没有 README 时不再整体失败。采集写出 0 条入榜集并在 `gaps` 说明原因与剔除数，校验按「实际数量」判断，既不会误杀 0 条产物，也不会把不足 10 条静默放过。预算耗尽与 404 判定沿用已按实际请求计数的实现。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 全部候选 README 均 404 时采集成功退出，写出 0 条入榜集
- [ ] `gaps` 说明入榜 0 条、README 缺失剔除数与预算耗尽情况
- [ ] 校验对采集产物接受 0 到 N 条，不足 10 条时按规格给出可见提示，不直接判失败
- [ ] 采集 CLI 测试覆盖「全部 404」与「不足 10 条」两种场景

**Acceptance evidence:** 回放服务器对所有候选的 README 返回 404，采集退出码为 0，产物 `github[]` 为空且 `gaps` 写明原因；校验该产物通过并提示不足 10 条。

## Comments
