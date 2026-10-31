# T32 开源准备

- 状态：进行中（2026-10-31）。两个仓库的历史已扫，没有发现密钥；公开方式已定（`decisions/2026-10-31-publication-choices.md`）；原始回包和 PR 评论未扫。
- 负责：协调会话统筹；题库侧 Codex；公开操作由用户执行
- 依赖：`decisions/2026-10-31-series-wrap-up.md`、`decisions/2026-10-31-license-check.md`
- 预算：0
- 边界：转为公开、推送到公开仓库由用户执行。硬规则「仓库不放题面」到公开时由用户解除，此前不变。

## 一、主仓库扫描结果（协调会话，2026-10-31，提交 `6a15ab9`）

范围：全部分支和 tag 的 691 个提交（含已删除文件和 `runs/`）、提交信息、227 个 PR 的标题和描述。

| 查什么 | 结果 |
|---|---|
| 密钥（DeepSeek/OpenAI 式 `sk-`、GitHub、AWS、Slack、私钥、写死的 Bearer） | 正则无命中。gitleaks 报 2 处，都是 `runs/20261018-T13-sql-direct-01*/SQL-R.jsonl` 第 202 行模型 SQL 里的 `q.ScenarioKey =`，判定误报 |
| 被忽略的数据（Parquet、chDB、原始回包、`.env`） | 历史里没有提交过 |
| 个人信息：本机路径 | `/Users/yuhuang` 共 8 处，都在 `decisions/isolation-check.md` |
| 个人信息：账号名 | `lalalagugugu` 4 处（`decisions/open-questions.md`、`reports/validation/t16_pr114_claude_review.md`、`reports/validation/t29-b1.md`、`tasks/T22b-l1plus-render-run.md`）；公开后本来可见 |
| 个人信息：邮箱 | 工作区没有；670 个提交的作者字段是用户的个人邮箱 |
| 工作相关姓名和 tracker 内容 | 无命中 |
| 提交信息里的会话链接 | 245 处，指向私有会话，别人打不开 |
| `docker-compose.yml` | 没有密码 |
| 仓库体积 | 工作区 939 个文件，GitHub 上约 13.7 MB |

未覆盖：`$SEMDEBT_DATA_DIR`（包括原始回包）。gitleaks 不扫合并提交和提交信息。

题库侧扫描见题库仓库 PR #23：密钥 0 命中；Cube 100 题都能追溯。主仓库 30 个文件含完整题面或参考 SQL：`runs/` 里是模型写出的 SQL 恰好包含相同字串；测试和 T16 校验文件里的短 SQL 没有逐个核对，题库公开后也无需隐藏；`semantic/tuning/` 和 T4 示例是设计内的调优题，核对 `reports/tuning/leakage-audit.md` 的题号，都不在留出集；`decisions/2026-10-17-semantic-gaps-and-realistic-questions.md` 含 Q14、Q36、Q89 的题面（Q13、Q28 为近似命中），盲模式设置没有禁读这个文件，T22 的本机会话记录里没有这个文件名。

## 二、公开方式

用户已定，见 `decisions/2026-10-31-publication-choices.md`。

## 三、公开前要做的事

- [x] gitleaks 扫主仓库（用户跑）
- [x] 查原始回包体积（用户跑）
- [x] 题库侧扫描：密钥、个人信息、题库外泄（题库侧 Codex）
- [x] 用户定第二节四项
- [x] 删掉工作区里的本机路径（`decisions/isolation-check.md` 改成 `<home>`；是历史记录，只改路径）
- [x] 重写 `README.md`；报告和回包的链接发布时补
- [ ] 报告引用的私有材料（`$SEMDEBT_DATA_DIR/v7-eval-20261030/`、`t31-v7-census-20261030/`）随回包一起放进 Release，先由用户确认范围并扫密钥，否则读者查不到出处
- [x] 主仓库加 `LICENSE`、`LICENSE-CONTENT.md`；`vendor/cube/NOTICE.md` 不用改
- [ ] 题库仓库：加许可文件，当前文件里的本机路径改成 `<home>`（题库侧 Codex）
- [x] 查 T22 盲写是否读过 `decisions/2026-10-17-semantic-gaps-and-realistic-questions.md`：本机 3 份 T22 会话记录里文件名出现 0 次，不用写进局限
- [x] 扫两个仓库的 PR 评论和 review（协调会话，正则查密钥、本机路径、邮箱、工作相关姓名）：无命中
- [x] 干净环境复现：由 Codex 新 clone 跑通重算和离线重评一个单元（`reports/validation/t32-clean-repro.md`）；缺口已补进 README。未登录访问等转公开后核对
- [ ] （T33）作答对照页：静态页面，同一题在各单元的查询、判定和不超过 20 行的结果并排；由脚本从日志和题库生成
- [ ] （T33）原始回包打包并扫密钥（取决于第二节）
- [ ] 报告里补上仓库和对照页链接
- [x] README 写明公开后这套题退役，不能再当留出题用
- [ ] 解除硬规则「仓库不放题面」，用户转公开，发布后从未登录的浏览器核对

## 记录（完成后填写）

- 产出：
- 偏离与理由：
- 工时：
