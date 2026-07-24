/**
 * 本机定时提醒调度：到点后回写网站，并（可选）触发设备唤醒链路。
 * 设备端应使用 self.schedule_reminder → Application::WakeWordInvoke → SendWakeWordDetected。
 */
"use strict";

const timers = new Map(); // matterId -> timeout handle

function log(msg) {
  console.log(`${new Date().toISOString()} - INFO - [reminder] ${msg}`);
}

function clearReminder(matterId) {
  const id = String(matterId);
  const t = timers.get(id);
  if (t) {
    clearTimeout(t);
    timers.delete(id);
  }
}

/**
 * @param {object} opts
 * @param {number|string} opts.matterId
 * @param {number} opts.delaySeconds
 * @param {string} opts.body
 * @param {string} opts.wakeText
 * @param {(method:string,path:string,body?:object)=>Promise<object>} opts.apiRequest
 */
function scheduleReminder(opts) {
  const matterId = opts.matterId;
  const delaySeconds = Math.max(1, Number(opts.delaySeconds) || 0);
  if (!matterId || !delaySeconds) return false;

  clearReminder(matterId);
  const ms = delaySeconds * 1000;
  log(`scheduled #${matterId} in ${delaySeconds}s · ${opts.body || ""}`);

  const handle = setTimeout(async () => {
    timers.delete(String(matterId));
    const wakeText =
      opts.wakeText ||
      `到点提醒：请温柔提醒用户「${opts.body || "一件事"}」。`;
    log(`FIRED #${matterId} · wakeText=${wakeText.slice(0, 80)}`);
    try {
      if (typeof opts.apiRequest === "function") {
        await opts.apiRequest("POST", `/api/mcp/reminders/${matterId}/fired`, {});
      }
    } catch (e) {
      log(`mark fired failed: ${(e && e.message) || e}`);
    }
    // 本机桥无法直接调用板端 WakeWordInvoke；到点后把文案写入待播队列，
    // 供 check_due_reminders / 设备侧定时器消费。设备烧录补丁后以板端定时为准。
    if (typeof opts.onFire === "function") {
      try {
        opts.onFire({ matterId, wakeText, body: opts.body });
      } catch (e) {
        log(`onFire error: ${(e && e.message) || e}`);
      }
    }
  }, ms);

  timers.set(String(matterId), handle);
  return true;
}

function listScheduled() {
  return Array.from(timers.keys());
}

module.exports = {
  scheduleReminder,
  clearReminder,
  listScheduled,
};
