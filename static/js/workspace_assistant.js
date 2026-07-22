(() => {
  const root = document.getElementById("ws-assistant");
  if (!root) return;

  const panel = document.getElementById("ws-assistant-panel");
  const toggle = document.getElementById("ws-assistant-toggle");
  const closeBtn = document.getElementById("ws-assistant-close");
  const form = document.getElementById("ws-assistant-form");
  const input = document.getElementById("ws-assistant-input");
  const sendBtn = document.getElementById("ws-assistant-send");
  const log = document.getElementById("ws-assistant-log");
  const status = document.getElementById("ws-assistant-status");
  const enabled = root.dataset.enabled === "1";
  const history = [];

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatRichText(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }

  function setOpen(open) {
    if (!panel || !toggle) return;
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    root.classList.toggle("is-open", open);
    if (open && input && enabled) input.focus();
  }

  function appendBubble(role, text) {
    if (!log) return;
    const div = document.createElement("div");
    div.className = `ws-bubble ws-${role}`;
    div.innerHTML = `<span class="ws-role">${role === "user" ? "我" : "助手"}</span><p>${formatRichText(text)}</p>`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function setBusy(busy) {
    if (input) input.disabled = busy || !enabled;
    if (sendBtn) sendBtn.disabled = busy || !enabled;
    if (status && busy) status.textContent = "正在查询真实用药数据…";
  }

  async function ask(message) {
    const text = (message || "").trim();
    if (!text || !enabled) return;
    appendBubble("user", text);
    const payloadHistory = history.slice(-8);
    setBusy(true);
    try {
      const resp = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: payloadHistory }),
      });
      const data = await resp.json();
      const reply = data.reply || "暂时无法回答，请稍后再试。";
      appendBubble("bot", reply);
      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: reply });
      if (history.length > 16) history.splice(0, history.length - 16);
      if (status) {
        const tools = (data.tool_trace || []).map((t) => t.name).filter(Boolean);
        status.textContent = tools.length
          ? `已调用：${tools.join(" → ")}`
          : "DeepSeek · 用药 + 任务清单";
      }
    } catch (_err) {
      appendBubble("bot", "网络异常，请稍后重试。");
      if (status) status.textContent = "请求失败";
    } finally {
      setBusy(false);
    }
  }

  if (toggle) {
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      setOpen(!open);
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", () => setOpen(false));

  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = input ? input.value : "";
      if (input) input.value = "";
      ask(value);
    });
  }

  document.querySelectorAll("[data-ws-quick]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setOpen(true);
      ask(btn.getAttribute("data-ws-quick") || "");
    });
  });
})();
