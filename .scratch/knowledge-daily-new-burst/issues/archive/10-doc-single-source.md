# 10: 文档单一来源收口

**What to build:** 技能与入口文件只留可解析的指针：引用 spec 真实存在的节名，不再指向「实现决策 · 排序与选取」这类不存在的小节；分析技能不再重复仓库字段清单，字段形状统一指向 schema。特性规格已归档并标记 delivered，主 spec 保持唯一产品口径。

**Blocked by:** 09

**Status:** done

- [x] 技能与入口文件中的 spec 指针都能在 spec 找到对应小节，不指向不存在的小节
- [x] 分析技能不再列举仓库字段，字段形状只指向 schema
- [x] 特性规格归档且状态为 delivered，主 spec 是唯一产品口径
- [x] 全仓检索确认同一字段清单没有同时出现在 schema 与技能中

**Acceptance evidence:** 逐个打开技能与入口文件里的 spec 指针，均能落到真实小节；把仓库字段清单与 schema 对照，技能侧已无重复列举。

## Comments
