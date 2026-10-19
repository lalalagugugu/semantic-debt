# T02 v2 第十三节修复及复验状态

- 已按主仓库 PR #118 修复 Q119 对象计数、selection 原因码与 Q92 阶段顺序，并补 Q122 隐藏对象编码回归。
- 真实语料 3,645 条重跑完成：47 处翻转（46+1），Q119 六条名次翻转已撤回；invalid_input / unscored / v2 timeout 均为 0。详情见 `scorer_v2_check.md`。
- 仍待 T05b 更新共用文件：194 条文件中 `t05b/name/selection-identity-wrong` 的 values 预期与第十三节 selection 裁定冲突。该只读输入未改，差异明确列出，不计通过。
- 参考自比上下文已从 T05b 报告查清：先去掉 selection；19 次探针通过。无需放宽完整参考域的 N+k 规则。
- 等待第十三节新共用用例及 T05b 最终独立复验；不打 harness-v1.1，不替用户启动重评。
