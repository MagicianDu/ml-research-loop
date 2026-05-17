# 外部 Pilot Feedback 收集说明

这个目录用于 stable release 前收集 **真实外部试用反馈**。README、schema、example 或模板文件不会被 `scripts/fresh_checkout_check.py --stable-readiness` 计入外部反馈数量。

## 计入口径

一条反馈只有同时满足以下条件，才会计入 stable readiness：

- 文件位于 `docs/pilot-feedback/` 或 `examples/pilot/feedback/`。
- JSON 字段 `feedback_type` 为 `external_pilot`。
- JSON 字段 `status` 为 `received`。
- JSON 字段 `source` 为 `external`。
- JSON 字段 `redacted` 为 `true`。
- `template` 和 `example` 不能为 `true`。
- 包含 `client`、`user_role`、`submitted_at`、`install_status`、`mcp_status`、`demo_status`。

## 为什么不能用模板代替

外部 pilot feedback 是产品稳定性证据，不是文档存在性证据。它应该证明真实用户在外部环境里尝试安装、接入客户端、运行 demo 或 benchmark probe，并能提供已脱敏反馈。没有真实用户反馈时，`missing_external_pilot_feedback` 必须继续保留。

## JSON 示例

```json
{
  "feedback_type": "external_pilot",
  "status": "received",
  "source": "external",
  "redacted": true,
  "client": "codex",
  "user_role": "graduate_student",
  "submitted_at": "2026-05-17T10:00:00Z",
  "install_status": "passed",
  "mcp_status": "passed",
  "demo_status": "passed",
  "summary": "External user completed MCP client acceptance and bounded demo.",
  "limitations": "Feedback is redacted and does not include private data."
}
```

提交前必须删除 token、私有路径、学生个人信息、未公开论文内容、私有 benchmark 数据和不可公开日志。
