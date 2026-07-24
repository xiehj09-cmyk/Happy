# 设备端到点提醒（WakeWordInvoke）

语音设定「30 秒后吃药」时，云端 MCP 写入网站代办，并指示小智调用设备工具：

```text
self.schedule_reminder(delay_seconds=30, message="到点提醒：请温柔提醒用户「吃药」。")
```

设备定时器触发后走完整唤醒链路：

`Application::WakeWordInvoke` → `BeginWakeWordInvoke` / `ContinueWakeWordInvoke` → `Protocol::SendWakeWordDetected`

## 固件改动位置（已写入本地 `D:\esp\xiaozhi-esp32`）

| 文件 | 改动 |
|------|------|
| `main/application.h` | 声明 `ScheduleReminder`，增加 reminder timer 成员 |
| `main/application.cc` | 实现 `ScheduleReminder`（`esp_timer` 到点调用 `WakeWordInvoke`） |
| `main/mcp_server.cc` | 注册 MCP 工具 `self.schedule_reminder` |

请重新编译并烧录固件后，设备工具列表里会出现 `self.schedule_reminder`。

## 云端（本仓库）

- `voice_note_write` / `schedule_voice_reminder`：写入代办并返回 `wake_text`
- 工具说明会要求模型**同时**调用 `self.schedule_reminder`
- 本机桥也会 `setTimeout` 回写 `reminded_at`，避免重复提醒
