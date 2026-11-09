# T33 发布物：作答对照页和原始回包

- 状态：已按用户 2026-11-09 明确授权发布 Release `midterm-v1` 及 GitHub Pages；附件匿名下载、哈希与线上页面核验通过。生成物来自已合并 PR #280，个人信息按既有裁决不脱敏。
- 负责：Codex
- 模式：主仓库 clone（`scripts/start-card.sh T33`），只读题库和 `$SEMDEBT_DATA_DIR`
- 依据：`decisions/2026-10-31-publication-choices.md`、`decisions/2026-10-26-answer-browser-idea.md`、`decisions/2026-10-31-license-check.md`
- 预算：0（不调用模型，不执行新查询）
- 边界：用户已公开仓库，并明确授权本次在 main 当前提交打 `midterm-v1` tag、直接发布 Release、创建 gh-pages 并开启 Pages，取代此前不发布的执行边界。仅 gh-pages 放已生成的对照页；main 不新增题面、参考答案或原始回包。本次状态 PR 只改任务卡和 BOARD，README 由协调会话更新；不调用付费模型。

## 一、作答对照页

读者选一道题和两个单元，并排看同一次作答。

- 静态页面，脚本从日志、题库和已有执行结果生成，不需要服务端。生成脚本进本仓库，生成结果放 `$SEMDEBT_DATA_DIR/publication/answer-browser/`；已原样部署至 `https://lalalagugugu.github.io/semantic-debt/`，来源为 gh-pages 分支根目录。
- 范围：`runs/20261031-T31-v5-rulings-01/` 的 19 个正式单元，主表 98 题，每题每单元 3 次可切换。
- 2026-11-09 新增独立本体批次：`20261104-T34-ontology-full-01` 的 SQL-L1、SQL-L1-onto、SQL-L1plus、SQL-L3a-full，各 98 题 × 3 次；判定只取 `runs/20261107-T34-final-01/`。逐页标明新版本模型同批次、与旧主表不直接比较，两批单元选择器相互隔离。旧 98 道题页保持不变，旧目录增加入口。
- 每次作答展示：题面、作答查询、声明的假设、最多 20 行结果、内容判定（准确率口径）、按约定交付判定。
- 不放模型思考内容、API 用量以外的原始响应字段、参考答案以外的第三方数据。
- 提供「同题两单元一对一错」和「三次时对时错」两个列表。
- 单文件体积要能在普通网络下打开；放不下就按题拆分。

## 二、原始回包和私有材料

清单及发布范围已获用户确认，PR #280 生成的两个 ZIP、manifest 和 SHA256SUMS 已原样作为 Release 附件发布。

- 回包：取 19 个正式单元实际用到的回包和执行结果。来源 run 以 T31 日志的 `source_run` 为准：`20261018-T13-sql-direct-01`、`20261019-C13-ladder-02`、`20261019-T13-l15s-v14-01`、`20261019-T15-explorer-01`、`20261019-T16-full-v14-json-01`、`20261019-T16-full-v14-sql-new-01`、`20261020-T15-explorer-l2e-02`、`20261020-T15-explorer-l2e-03`、`20261025-T14-tuned-01`、`20261025-T22b-l1plus-l3a-03`、`20261025-T30-combo-01`。按单元筛，不整 run 打包。
- 2026-11-01 用户更新：同一回包包另加 `20261031-T29-u2-v3-01` 的 `SQL-L0`、`SQL-L1`、`SQL-L0-u2`、`SQL-L1-u2`、`SQL-L0-u2p`、`SQL-L1-u2p`，各 98 题 × 3 次，共 1,764 次，含思考内容和执行结果。以采集核验报告固定的完整源日志 SHA-256 为准，只收 done 作答引用的实际文件；对照页仍仅 19 单元。
- 2026-11-09 用户更新：保留上述包内全部文件，加入 `20261104-T34-ontology-full-01` 四单元各 109 题 × 3 次，共 1,308 次的全部原始响应和执行结果，含思考内容。U2 仍不加入对照页；本体四单元按上节独立批次展示。
- 私有材料：报告出处引用的 `v7-eval-20261030/`、`t31-v7-census-20261030/` 里实际被引用的文件。
- 本体私有材料：补入四单元 materials.json 和含理由的 codex-decisions.json、SQL-L1-onto 和 SQL-L3a-full 两份实际 system.txt、定稿绑定的 locked-verdicts.json / review-identity-map-non-v2-v2.json / review-note-audit-final.json，以及 Claude `t34-run-20261104/claude-review/results.json` 全文（含全部 note；SHA-256 `1634d223b90257bb7843a24cd879e000b20a0f1a98b1acba0de0e9803e8c96a9`）。14 个新增文件进入 t33-cited-private.zip，不将题面或参考答案写入仓库。
- 对压缩包内容跑 gitleaks，并查本机路径、邮箱和 `DEEPSEEK_API_KEY`。报告只写文件名和类别，不贴匹配值。
- 输出：`$SEMDEBT_DATA_DIR/publication/` 下的压缩包和 sha256，文件清单和体积写进报告 `reports/validation/t33-publication-artifacts.md`。

## 验收

- 重新运行生成脚本，对照页和压缩包内容不变。
- 对照页的判定计数和 `reports/results/accuracy-v5-cells.csv` 逐单元一致。
- 本体批次四单元内容判对数 234 / 235 / 269 / 275，与 `runs/20261107-T34-final-01/summary-final.json` 一致；复核 174 项及全部 note 与指定哈希一致。
- 抽查对照页和压缩包，确认对照页没有思考内容，两者都没有密钥。
- 报告列明压缩包含思考内容，由用户确认后才发布。
- Release 非草稿、非预发布，tag 指向发布时的 main；匿名打开 Release、实际下载附件核对哈希，线上 198 页逐一与 manifest 匹配。

## 记录（完成后填写）

- 产出：`scripts/t33_publication_artifacts.py`、9 项针对性测试及完整验证报告；回包包 27,421 文件／62,917,954 字节，较上版新增 3,294 文件／8,409,604 压缩字节；引用材料包 25 文件／6,965,210 字节，新增 14 文件／6,646,419 压缩字节。两批对照页共 198 页、6,615 次作答；旧包内文件逐项保留。全部产物在外部 publication 目录，manifest、SHA256SUMS 已更新，重复生成逐字节一致；全量扫描 15 项通用密钥命中均为已核对 SQL 误报，未复核项 0。测试及布局检查 53 passed / 1 skipped。
- 偏离与理由：用户已确认 T4 只跑 49 道留出题，保留 98 题导航，其余题标注「未运行（T4 只跑留出题）」；不补跑。生成阶段复用主工作区已有 Python 环境，未添加依赖。此前 file 协议限制在发布后改为 HTTPS 线上核验，已实测目录、本体入口、双栏及次数切换。文本附件常规下载链路遇到 HTTP 504，使用官方匿名附件 API 实际下载成功，详见发布记录。
- 工时：未计时；本卡模型调用与新增查询均为 0。

## 用户确认

- [x] 用户授权按 2026-11-09 更新扩容回包和定稿证据，保持原包内容，含思考内容；完整文件清单供 PR 审阅。
- [x] 用户已确定引用材料包随 Release 发布，包括本体系统消息、Codex 含理由判定和 Claude 含 note 的完整复核结果；本次已获明确发布授权并执行。
- [x] 邮箱形式文本和本机路径按既有裁决原样保留；本次新增两份本体系统消息的邮箱形式匹配，报告只记文件名和类别。
- [x] 用户已公开仓库并授权直接发布；Release、gh-pages 和 Pages 已就绪，线上页面及附件已匿名核验。README 留给协调会话。

## 发布记录（2026-11-09）

- Release：[midterm-v1](https://github.com/lalalagugugu/semantic-debt/releases/tag/midterm-v1)，非草稿、非预发布，发布于 2026-11-09 13:33:42（Asia/Singapore）。说明列明主表、第 9 节、本体对照三批；本体批次为新版本模型，与主表不直接比较；文件清单和 SHA-256 见附件。
- tag 目标为发布时 main：`12c17495f52ed0c9b475554524459bb351d89d19`（包含 PR #280）。未移动已有 tag，未改变任何生成物。
- Pages：[作答对照页](https://lalalagugugu.github.io/semantic-debt/)，本体入口为 [t34/](https://lalalagugugu.github.io/semantic-debt/t34/)。gh-pages 提交 `879b5e3a090c1b9d584ddfc970dd5063c73a814e`，仅含 198 个已核验 HTML 和空 `.nojekyll`。分支式构建已成功，来源 `gh-pages:/`，HTTPS 已开启。

| Release 附件 | 字节数 | SHA-256 |
|---|---:|---|
| t33-formal-raw.zip | 62,917,954 | `8a686853fee56eb081ace05c271042e60ee1e3bf14bc38ca74e0fc4c3ef84834` |
| t33-cited-private.zip | 6,965,210 | `ee4f95890ca4e34542ba3ef368757ac49b094ba13c6819e30958066f3801302f` |
| t33-manifest.json | 7,353,844 | `c99eddd80da30d593fe263fed8fb217670ef53cb7b5361b9312eec4e3de894ec` |
| t33-SHA256SUMS | 173 | `49aae1502bebea55c83881222d83fa6bfada47273f9073da42df6573c369cc7b` |

未登录核验结果：

- 请求使用 `curl -q`，显式清空 Authorization 和 Cookie，不使用 gh 下载附件，不带 GitHub 登录凭据。Release 页返回 HTTP 200。
- 两个 ZIP 均从公开浏览器下载地址实际下载成功；其 SHA-256 与下载到的 SHA256SUMS、下载到的 manifest 及 PR #280 本地产物全部一致。
- manifest 和 SHA256SUMS 的常规浏览器下载链路多次返回网关 HTTP 504；通过 GitHub 官方公开附件 API，以 `Accept: application/octet-stream` 且不带认证或 Cookie 实际下载，均返回 HTTP 200，字节与本地文件一致。这两项不记为常规下载路径已通过。
- 使用的匿名文本附件 API 为 [manifest](https://api.github.com/repos/lalalagugugu/semantic-debt/releases/assets/726356898) 和 [SHA256SUMS](https://api.github.com/repos/lalalagugugu/semantic-debt/releases/assets/726356896)；下载时需要上述 Accept 头。
- 对照页全部 198 个 HTML 都经匿名 HTTPS GET 核对，字节数和 SHA-256 与 Release manifest 一致。浏览器实际打开旧目录、本体目录和本体 Q01 双栏页，次数切到第 2 次后两栏均显示本体 run 第 2 次结果；四单元选择器及版本提示正常。
- 本次仅发布已扫描产物及执行线上验证，无付费模型调用，无新增查询，README 未改。
