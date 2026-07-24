# 设备端到点提醒（WakeWordInvoke）

官方限制：`listen.detect` 的 `text` **只能是短唤醒词**，长句会被云端拒绝（报「文本太长」）。

正确示例：

```text
self.schedule_reminder(delay_seconds=30, message="提醒喝水")
```

错误示例（勿用）：

```text
message="到点提醒：请温柔提醒用户「喝水」。"
```

到点链路：`ScheduleReminder` → `WakeWordInvokeForced` → `SendWakeWordDetected(短词)`

建议在小智控制台「角色介绍」加一句：  
「若用户说法以『提醒』开头（如提醒喝水），请立刻用简短口语提醒该事项。」
