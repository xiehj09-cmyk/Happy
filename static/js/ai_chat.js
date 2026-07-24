(() => {
  const app = document.getElementById("ai-chat-app");
  if (!app) return;

  const logEl = document.getElementById("ai-chat-log");
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("ai-chat-input");
  const resetBtn = document.getElementById("ai-chat-reset");
  const chatUrl = app.dataset.chatUrl;
  const enabled = app.dataset.enabled === "1";
  const opening = app.dataset.opening || "您好，想聊点什么？";

  /** @type {{role:string, content:string}[]} */
  let history = [];

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function appendBubble(role, text) {
    const div = document.createElement("div");
    div.className = `chat-bubble chat-${role === "assistant" ? "ai" : "user"}`;
    const label = role === "assistant" ? "陪伴助手" : "您";
    div.innerHTML = `<span class="chat-role">${label}</span><p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>`;
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function resetChat() {
    history = [];
    logEl.innerHTML = "";
    appendBubble("assistant", opening);
  }

  async function parseResponse(res) {
    const raw = await res.text();
    let data = null;
    try {
      data = raw ? JSON.parse(raw) : null;
    } catch (_e) {
      const snippet = (raw || "").replace(/\s+/g, " ").slice(0, 120);
      throw new Error(
        res.status >= 500
          ? `服务暂时无响应（${res.status}）。若刚部署，请稍等再试；并确认已配置 DEEPSEEK_API_KEY。`
          : res.status === 401 || res.status === 403
            ? "登录已失效，请刷新页面后重新登录。"
            : `返回格式异常（${res.status}）${snippet ? "：" + snippet : ""}`
      );
    }
    if (!res.ok) {
      const msg =
        (data && (data.reply || data.error)) ||
        `请求失败（${res.status}）`;
      throw new Error(msg);
    }
    return data || {};
  }

  async function sendMessage(text) {
    const msg = String(text || "").trim();
    if (!msg || !enabled) return;
    appendBubble("user", msg);
    input.value = "";
    input.disabled = true;

    // 只把「已完成的轮次」作为历史；当前句单独放在 message，避免重复
    const prior = history.slice(-10);

    try {
      const res = await fetch(chatUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        credentials: "same-origin",
        body: JSON.stringify({ message: msg, history: prior }),
      });
      const data = await parseResponse(res);
      const reply = (data && data.reply) || "我在听，您慢慢说。";
      appendBubble("assistant", reply);
      history.push({ role: "user", content: msg });
      history.push({ role: "assistant", content: reply });
      if (history.length > 20) history = history.slice(-20);
    } catch (e) {
      const tip = (e && e.message) || "暂时连不上陪伴助手，请稍后再试。";
      appendBubble("assistant", tip);
    } finally {
      input.disabled = !enabled;
      if (enabled) input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(input.value);
  });

  if (resetBtn) resetBtn.addEventListener("click", resetChat);

  document.querySelectorAll(".companion-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!enabled) return;
      sendMessage(btn.dataset.prompt || btn.textContent);
    });
  });

  resetChat();
})();
