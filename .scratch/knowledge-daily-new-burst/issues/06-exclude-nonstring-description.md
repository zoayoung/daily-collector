# 06: 非字符串 description 的排除口径

**What to build:** description 不是字符串（数字、对象、布尔等）时视为无描述并硬剔除，规格把该情形并入「无描述」的定义。排除规则、测试与文档对同一条仓库给出同一结论。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 工作流 spec 的候选排除段把「非字符串 description」纳入无描述的定义
- [ ] 采集对数字、对象、`null`、缺失的 description 均剔除
- [ ] 采集 CLI 测试覆盖非字符串 description
- [ ] Awesome 名称与「a curated list」开头的既有排除行为不变

**Acceptance evidence:** 回放服务器返回一条 `description` 为数字的仓库，采集产物中不含该条，`stats.excluded` 计入。

## Comments
