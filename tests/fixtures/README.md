# 外部契约快照

这里是 GitHub API 的真实返回，作为采集解析的**事实来源**：解析代码按这些快照测，API 变形状时测试先红。

| 文件 | 来源 | 抓取日期 |
| --- | --- | --- |
| `search_repositories.json` | `GET /search/repositories?q=pushed:>=2026-10-21+stars:>=100&sort=stars&order=desc&per_page=3` | 2026-10-22 |
| `star_history.json` | `GET /repos/public-apis/public-apis/stargazers/history` | 2026-10-22 |

- 抓取时带 `GITHUB_TOKEN` 认证，字段与线上一致；只裁剪了 `per_page`，没有改字段。
- `star_history.json` 按周分桶：`{week, total, days[7]}`，`days[i]` 是周起点第 i 天的新增 star。测试据此断言 2026-10-21 当日新增为 152。
- 更新快照时同步改抓取日期与被测的期望值（`tests/test_collect.py` 的 `FIXTURE_GAIN`）。
