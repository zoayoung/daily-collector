# 04: token 报告 markdown

**What to build:** 每次运行结束后，除机器可读的 token 统计外，同时生成一份人可读的 markdown 报告，放在日报目录下的 `tokens/` 中。报告按每次 run 分节，列出各代理的消息数、input、output、cache 读写、reasoning 与成本，并在末尾给出当日合计；所有数值与机器可读统计完全一致。无运行数据时不生成报告。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 一次运行后出现当日 token markdown 报告，文件名与当日日报对应。
- [ ] 报告按 run 分节，并按主代理、分析、整理列出表格。
- [ ] 报告末尾给出当日消息数、各项 token 与成本合计。
- [ ] 报告数值与机器可读统计逐项一致，不改写、不估算缺失值。
- [ ] 没有运行数据或统计不可读时不生成报告，由主代理在汇报中说明。
