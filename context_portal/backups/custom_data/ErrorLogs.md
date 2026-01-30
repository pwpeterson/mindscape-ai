# Custom Data: ErrorLogs

### 2026-01-12_conport_sync_double_tool_invocation

*   [2026-01-12 16:35:49]

```json
{
  "timestamp": "2026-01-12T16:35:26.792Z",
  "issue": "Tool call rejected: only one tool may be used per message",
  "context": "During ConPort sync kickoff, attempted multiple list_directory calls in one assistant message; second call was rejected by tool runner.",
  "impact": "No data loss; proceeded with single list_directory result and continued sync."
}
```
