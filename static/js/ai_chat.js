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

  async function sendMessage(text) {
    const msg = String(text || "").trim();
    if (!msg || !enabled) return;
    appendBubble("user", msg);
    history.push({ role: "user", content: msg });
    input.value = "";
    input.disabled = true;

    try {
      const res = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, history }),
      });
      const data = await res.json();
      const reply = (data && data.reply) || "我在听，您慢慢说。";
      appendBubble("assistant", reply);
      history.push({ role: "assistant", content: reply });
      if (history.length > 20) history = history.slice(-20);
    } catch (_e) {
      appendBubble("assistant", "网络有些不稳，请稍后再试。");
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
