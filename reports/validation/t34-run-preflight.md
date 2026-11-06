# T34 第 4–6 步：运行预检与待批准命令

预检日期：2026-11-04；标签发布与正式 dry-run：2026-11-05。分支：`T34-run`。计划 run-id：`20261104-T34-ontology-full-01`。**尚未付费运行，模型 API 调用 0**。第 3 步已通过（#265）；这里只准备采集、判定和报告，不改语义、提示、评分器或判定规则。

## 当前检查结果

- 已完成上次 `git pull origin T34-work`，吸收 `e08f7a7`；本阶段从已合并的 `origin/main`（`51247a8`）建分支。
- 2026-11-04 的原样 CLI dry-run 曾因缺标签退出 2；失败记录保留在结构化预检的 previous_cli_dry_runs 与 INDEX，未绕过版本检查。
- 2026-11-05 用户明确授权创建标签后，每条命令单独执行 fetch、附注打标、push、ls-remote；远端确认 tag 对象 `c3750ae8e5fdecfb3304d7b73a7067d28fe40b39`，解引用提交为 **`51247a8c5e4e296093b4260a17db843ff64c06d8`**，不是 fd920f3。T34 目录也已 fetch 到标签。
- **正式 CLI dry-run 已通过，退出 0**：题库及语义版本验证成功；四单元 1,308 次作答、预计 1,440 次调用、错峰 23.8252158 元。当前只待用户批准付费，模型 API 调用仍为 0。
- 预检结构化证据：`runs/20261104-T34-ontology-full-01/preflight.json`，只含参数、题号/题面哈希、文件哈希与数量，不含题面、参考答案、响应内容或密钥。

## 与主表一致的采集配置

主表 SQL-L1plus 的源运行是 `20261025-T22b-l1plus-l3a-03`：109 题（跳过 judge）× 3 次，并发 4，执行超时 120 秒，模型 `deepseek-flash`，思考 high；不设置 temperature，保留原生一次 SQL 修正及默认传输重试。原日志的 327 条身份、重复次数、题面哈希、执行超时与资源限制已核对；并发及原始 `--est-from-args` 取该 run 在 `runs/INDEX.md` 的完成记录。

四个单元均采集同样的 109 题 × 3 次，同一个 run。主表分析只取 `runs/20261031-T31-v5-rulings-01` 的 98 题（每单元 294 次），不报告 109 题准确率，不另取 49 题。

题库使用原采集配置的只读快照 `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，tag `eval-v1.2` = `90e13b385a639a9164ac78430c50c11a7859f976`，原生 tag 校验已通过；109 道输入题面的 SHA-256 与主表 L1plus 的源日志全部相同，四个单元的输入集合也相同。后续最终内容判定按主表 D1 的现行裁定与参考，不把采集时的自动分数当最终准确率。

两个文字上下文与 `semantic-v1.6-l1plus` 的历史渲染结果逐字节比较相同；相关源文件和旧渲染共用代码也未变。同时核对原始采集日志的完整系统消息哈希：

| 单元 | 上下文文件 SHA-256 | 完整系统消息 SHA-256 | 结论 |
|---|---|---|---|
| SQL-L1 | `5585014ac612da15dd62c3d22bbf254608ee420311fa455a9f9a10612fd2b48e` | `8df43ae0552cab461d8bd490ff4e21114995681ff0ccd38cf85115f65e44f6a6` | 上下文字节相同；系统消息与原 T13 源日志全部相同。 |
| SQL-L1plus | `2a1929b22a94e72adaa4f16441f5caabd61308ebb0399aa5760dc112295b8112` | `b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3` | 上下文字节相同；系统消息与原 T22b 源日志全部相同。 |

已用 `render.context` 渲染四份上下文并确认不陈旧；没有运行会重写对应报告的完整渲染入口。主目录与 T22b 既有 Python 环境均为 Python 3.12.13、chDB 4.4.0、PyYAML 6.0.3。默认执行器在无模型调用的只读预检中成功查询日期表行数 2,556；未改执行器路径或套包装脚本。

## 正式 CLI dry-run（已通过，待付费批准）

正式 `python -m harness.run_direct --dry-run` 通过，结果与此前原生估价函数一致；使用与主表相同的 `--est-from-args` 参数：修正率 10%、每次输出 3,000 token、缓存命中率 95%、题面 60 token。2026-11-04 核对 [DeepSeek 官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)，错峰单价与冻结 harness 一致：缓存命中 0.02、未命中 1、输出 4 元/百万 token。没有更改代码中的价格。

| 单元 | 题数 | 作答次数 | 预计调用 | 预计输入 token/调用 | 错峰预计元 |
|---|---:|---:|---:|---:|---:|
| SQL-L1 | 109 | 327 | 360 | 41,144 | 5.34 |
| SQL-L1-onto | 109 | 327 | 360 | 58,175 | 5.77 |
| SQL-L1plus | 109 | 327 | 360 | 66,758 | 5.98 |
| SQL-L3a-full | 109 | 327 | 360 | 97,418 | 6.74 |
| 合计 | 4 × 109 | **1,308** | **1,440** | — | **23.8252158（约 23.83）** |

调用数含预估的一次 SQL 修正；不把它当成实际调用或已支出。CLI 的普通单元 `--budget 25` 检查的是估算，不是运行时硬额度账本；原 T22b 也未启用会改变传输重试的额度预留模式。本阶段保留原样 harness 和重试参数，不另加监督脚本或预算补丁。实际调用、usage、原生传输重试及未知费用会按原日志完整核算，不将未知当 0。

## 已通过的原样 dry-run 命令

下列命令已于 2026-11-05 退出 0；冻结标签及四份上下文均经原生验证。沿用昨日登记且尚未采集的 run-id，不覆盖任何既有结果。`--dry-run` 阶段移除 API 凭据：

```sh
env -u DEEPSEEK_API_KEY \
  SEMDEBT_EVAL_DIR="$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2" \
  UV_CACHE_DIR="$TMPDIR/uvcache" \
  uv run --no-project --python "$SEMDEBT_MAIN_DIR/.venv/bin/python" \
  python -m harness.run_direct \
  --cell SQL-L1 --cell SQL-L1-onto --cell SQL-L1plus --cell SQL-L3a-full \
  --run-id 20261104-T34-ontology-full-01 --model deepseek-flash \
  --skip-judge --reps 3 --concurrency 4 --exec-timeout 120 \
  --eval-tag eval-v1.2 --semantic-tag semantic-v1.7-l3a-full \
  --budget 25 --est-from-args --dry-run
```

完整 dry-run 已通过；用户批准后，付费命令使用同样参数，恢复环境中的 API 凭据并只去掉 `--dry-run`。会发送这 109 道私有题面及对应语义上下文到 DeepSeek 官方 API；执行报错的原生修正会带模型 SQL 与执行报错，不发送参考答案。批准前不运行包括“查指纹”在内的任何付费探针。

首次响应作为本 run 的指纹基准并记录，不把主表 `e72d3c7f663d3e1383b00b3884cb4501` 或 10-31 的 `bc19ba97…` 写成必须相等的期望值。使用原生 FingerprintGuard 在同一 run 的全部单元间检测变化，变更时停止继续派发，保留已经在途的请求及其日志；不套监督脚本。

仅在北京时间工作日 12:00–14:00、18:00 后或周末运行，不传 `--allow-peak`；原生 CallBoundary 在每次发送前检查时段，到高峰就停，后续同 run 只补缺。恢复前重核上下文哈希、指纹状态与已有作答身份。

## 判定及报告安排（尚未开始）

采集后全量核对逐次身份、API 原包和执行包哈希、返回结果及最终标签；按主表 D1 的内容规则、R1–R11 及后续用户裁定执行，不改评分规则。原始内容与独立判定材料留 `$SEMDEBT_DATA_DIR`；仓库只存题号、标签、哈希、数字和不含题面的理由。判对部分交独立 Claude Code 会话复核，差异逐项解决后再定稿。

`reports/results/l3a-full.md` 在采集和复核完成后生成，当前不填假结果。范围为四单元的 98 题：

- 分别比较 SQL-L1-onto 减 SQL-L1、SQL-L3a-full 减 SQL-L1plus；不比较这两个差的大小。
- 新 SQL-L1、新 SQL-L1plus 分别与主表最终 D1 标签比较，明确指纹变化。
- 按题配对 bootstrap 5,000 次、seed 0，沿用主表 `scripts/t31_v4_recompute.py:paired_interval` 的题均值、随机数和经验分位点方法。
- 各单元准确率、三次全对/全错/时对时错、首轮报错率、token、费用与三类错因（怎么算、是什么/属于谁、SQL）分别报告。
