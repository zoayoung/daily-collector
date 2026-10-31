# 03: 候选排除规则与 excluded 统计

**What to build:** 候选集不再被 Awesome 列表和空描述仓库占用候选位与增量预算。采集在搜索去重与通道计数之后、30 天重复窗口过滤之前，硬剔除两类候选：仓库名（`full_name` 的 repo 段）包含 `awesome`（不区分大小写），或描述以 `a curated list` / `curated list` 开头（不区分大小写）；描述缺失、为空或去空白后为空。剔除数量写入新增的可选统计字段 `excluded`，统计恒等式变为 `候选总数 - excluded - 窗口剔除数 = eligible`；旧产物缺该字段时按 0 校验。`gaps` 中以现有风格记录排除数量。

**Blocked by:** 01（同一份采集统计契约与候选管线）

**Status:** done

- [x] 候选集阶段硬剔除 Awesome 列表：仓库名含 `awesome`，或描述以 curated list 开头（均不区分大小写）
- [x] 候选集阶段硬剔除无描述仓库：缺失、`null` 或去空白后为空
- [x] 实施顺序为「搜索去重 → 通道计数 → 排除 → 重复窗口过滤 → eligible」，通道计数仍等于候选总数
- [x] 采集统计新增可选 `excluded`（非负整数），满足 `candidates - excluded - dropped_recent_duplicates = eligible`
- [x] 校验按上述恒等式校验；旧产物无 `excluded` 时按 0 处理并继续通过
- [x] `gaps` 以现有文案风格记录被排除的数量
- [x] 测试通过采集与校验 CLI 验证：两类排除命中、统计恒等、旧产物兼容

**Acceptance evidence:** 回放响应中放入 Awesome 列表、无描述仓库与正常仓库，采集产物只保留正常仓库，统计恒等式成立；删除 `excluded` 的旧产物仍校验通过。

## Comments
