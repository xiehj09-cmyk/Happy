(() => {
  const select = document.getElementById("add-catalog-select");
  const doseInput = document.getElementById("add-dose");
  const timeInput = document.getElementById("add-time");
  const preview = document.getElementById("catalog-preview");

  function syncCatalog() {
    if (!select) return;
    const option = select.selectedOptions[0];
    if (!option || !option.value) {
      if (preview) preview.hidden = true;
      return;
    }
    if (doseInput && option.dataset.dose) {
      doseInput.value = option.dataset.dose;
    }
    if (timeInput && option.dataset.time) {
      timeInput.value = option.dataset.time;
    }
    if (preview) {
      preview.hidden = false;
      preview.textContent = option.dataset.effect
        ? `作用效果：${option.dataset.effect}`
        : "";
    }
  }

  if (select) {
    select.addEventListener("change", syncCatalog);
  }

  document.querySelectorAll("[data-pick-catalog]").forEach((link) => {
    link.addEventListener("click", () => {
      const id = link.getAttribute("data-pick-catalog");
      if (select && id) {
        select.value = id;
        syncCatalog();
      }
    });
  });

  // —— DeepSeek 智能加药聊天 ——
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("ai-chat-input");
  const sendBtn = document.getElementById("ai-chat-send");
  const log = document.getElementById("ai-chat-log");
  const status = document.getElementById("ai-chat-status");

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

  function appendBubble(role, text, meta) {
    if (!log) return;
    const div = document.createElement("div");
    div.className = `ai-bubble ai-${role}`;
    const roleLabel = role === "user" ? "家属" : "助手";
    let body = `<span class="ai-role">${roleLabel}</span><p>${formatRichText(text)}</p>`;
    if (meta) {
      body += `<small class="ai-meta">${escapeHtml(meta)}</small>`;
    }
    div.innerHTML = body;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function setBusy(busy) {
    if (input) input.disabled = busy;
    if (sendBtn) sendBtn.disabled = busy;
    if (status && busy) {
      status.textContent = "正在联网检索说明书并由 DeepSeek 整理…";
    }
  }

  if (form && input) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;

      appendBubble("user", message);
      input.value = "";
      setBusy(true);

      try {
        const resp = await fetch("/api/medication/ai-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });
        const data = await resp.json();
        const reply = data.reply || "暂时无法处理，请稍后重试。";
        let meta = "";
        if (data.added && data.proposal) {
          const p = data.proposal;
          meta = [
            p.drug_name && `药名 ${p.drug_name}`,
            p.alias && `别名 ${p.alias}`,
            p.category && `类型 ${p.category}`,
            p.schedule_time && `时间 ${p.schedule_time}`,
            p.dose && `剂量 ${p.dose}`,
          ]
            .filter(Boolean)
            .join(" · ");
        } else if (data.proposal && data.proposal.drug_name) {
          meta = `草案：${data.proposal.drug_name}（未入库）`;
        }
        if (data.disclaimer) {
          meta = meta ? `${meta} · ${data.disclaimer}` : data.disclaimer;
        }
        appendBubble("bot", reply, meta);
        if (status) {
          status.textContent = data.added
            ? "已写入老人药单，可在「今日记录」查看。"
            : "模型：DeepSeek V4 Flash（已关闭深度思考，优先速度）";
        }
        if (data.added) {
          window.setTimeout(() => window.location.reload(), 1200);
        }
      } catch (err) {
        appendBubble("bot", "网络异常，请稍后重试。");
        if (status) {
          status.textContent = "请求失败，请检查网络或稍后重试。";
        }
      } finally {
        setBusy(false);
        if (input) input.focus();
      }
    });
  }
})();
