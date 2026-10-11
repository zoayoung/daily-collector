# 领域文档

工程类技能在探索本仓库时，应如何消费本仓库的领域文档。

## 探索前先读这些

- 根目录的 **`GLOSSARY.md`**，或
- 根目录的 **`GLOSSARY-MAP.md`**（若存在）：它指向每个上下文各自的 `GLOSSARY.md`，读取与当前主题相关的那些。
- **`docs/adr/`**：读取涉及你即将动手区域的 ADR。

若这些文件不存在，**静默继续**。不要提示缺失，也不要预先建议创建。`/domain-modeling` 技能（经 `/grill-with-docs` 与 `/improve-codebase-architecture` 到达）会在术语或决策真正落定时按需创建。

## 文件结构

单上下文仓库（绝大多数仓库，本仓库即属此类）：

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

多上下文仓库（根目录存在 `GLOSSARY-MAP.md`）：

```
/
├── GLOSSARY-MAP.md
├── docs/adr/                          ← 全系统决策
└── src/
    ├── ordering/
    │   ├── GLOSSARY.md
    │   └── docs/adr/                  ← 上下文专属决策
    └── billing/
        ├── GLOSSARY.md
        └── docs/adr/
```

## 使用词汇表的词汇

当你的产出命名某个领域概念时（议题标题、重构提案、假设、测试名），请使用 `GLOSSARY.md` 中定义的术语。不要漂移到词汇表明确回避的同义词。

若你需要的概念尚未进入词汇表，这是一个信号：要么你在发明项目不使用的语言（重新考虑），要么存在真实缺口（记下以便 `/domain-modeling` 处理）。

## 标记 ADR 冲突

若你的产出与既有 ADR 矛盾，请显式暴露，而非默默覆盖：

> _与 ADR-0007（事件溯源订单）矛盾，但值得重新开启，因为……_
