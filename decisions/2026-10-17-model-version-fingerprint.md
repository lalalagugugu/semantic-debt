# 2026-10-17 模型版本以 `system_fingerprint` 为准

- 裁决人：用户，2026-10-17（协调会话提案）
- 约束：T11（harness）、T12、G3（`harness-v1`）、T13 起的全部正式运行
- 依据：`runs/20261017-T11-smoke-1017-01`（PR #64）

## 背景

DeepSeek 把 V4.1 Flash 1017 直接挂在原调用名 `deepseek-flash` 下。T11 复测发现：接口返回的 `model` 字段**只是回显调用名**，新旧两次都是 `deepseek-flash`；真正变了的是 `system_fingerprint`（`aeb56401…` → `e72d3c7f…`），而 harness 目前没记它。也就是说，按现有日志，调用名背后换了模型是**看不出来的**——全量跑到一半被换掉，结果会静默混进两个模型。

## 裁决

1. harness 每次调用记录 `system_fingerprint`（T11 遗留项，G3 之前合并）。
2. T12 选定模型时同时记下当时的指纹；G3 把它写进 `decisions/model.md`。
3. 正式运行中，指纹与 G3 记下的不同：**停下问用户**，不自动判废、不静默继续。指纹也可能因服务端部署变化而变、模型未变，由用户结合 DeepSeek 的公告判断；判定换了模型，从换的那一刻起的结果另起 run，不与之前混算。
4. 日志的 `model_version` 字段保留，但不再当作版本证据。
