(() => {
  const app = document.getElementById("cst-chat-app");
  if (!app) return;

  const logEl = document.getElementById("chat-log");
  const stageEl = document.getElementById("visual-stage");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const resetBtn = document.getElementById("chat-reset");
  const chatUrl = app.dataset.chatUrl;
  const sessionNum = Number(app.dataset.sessionNum || 1);
  const opening = app.dataset.opening || "您好，欢迎开始 CST。";

  let turn = 0;

  function escapeHtml(str) {
    return String(str)
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

  function appendBubble(role, text) {
    const div = document.createElement("div");
    div.className = `chat-bubble chat-${role}`;
    div.innerHTML = `<span class="chat-role">${role === "ai" ? "CST 引导员" : "您"}</span><p>${formatRichText(text)}</p>`;
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function showCard(card) {
    if (!card) {
      stageEl.innerHTML = `<p class="visual-placeholder">继续聊聊文字话题…</p>`;
      return;
    }
    stageEl.innerHTML = `
      <article class="visual-card visual-card-large">
        <div class="visual-card-emoji">${card.emoji || "🖼️"}</div>
        <div>
          <strong>${escapeHtml(card.label || "")}</strong>
          <p class="visual-card-caption">${escapeHtml(card.caption || "")}</p>
        </div>
      </article>`;
    document.querySelectorAll(".mini-card").forEach((el) => {
      el.classList.toggle("is-active", el.dataset.cardId === card.id);
    });
  }

  async function sendMessage(text) {
    if (text) {
      appendBubble("user", text);
      turn += 1;
    }
    input.value = "";
    input.disabled = true;

    try {
      const res = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, turn, session_num: sessionNum }),
      });
      const data = await res.json();
      if (data.reply) appendBubble("ai", data.reply);
      if (data.visual_card) showCard(data.visual_card);
    } catch (_e) {
      appendBubble("ai", "网络有些问题，请稍后再试，或请家属陪同继续。");
    } finally {
      input.disabled = false;
      input.focus();
    }
  }

  function startChat() {
    logEl.innerHTML = "";
    turn = 0;
    showCard(null);
    appendBubble("ai", opening);
    sendMessage("");
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    sendMessage(text);
  });

  resetBtn.addEventListener("click", startChat);
  startChat();
})();
