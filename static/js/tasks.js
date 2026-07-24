(() => {
  const root = document.getElementById("tasks-root");
  if (!root) return;

  const role = root.dataset.role || "elder";

  function actionId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return `a-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function api(url, body) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || data.ok === false) {
      const err = new Error(data.error || "操作失败");
      err.data = data;
      throw err;
    }
    return data;
  }

  function renumber(list) {
    list.querySelectorAll(".step-editor-row").forEach((row, i) => {
      const num = row.querySelector(".step-editor-num");
      if (num) num.textContent = String(i + 1);
      const remove = row.querySelector("[data-remove-step]");
      if (remove) remove.hidden = list.querySelectorAll(".step-editor-row").length <= 1;
    });
  }

  function bindStepEditor(list, addBtn) {
    if (!list) return;
    function addRow(value) {
      const row = document.createElement("div");
      row.className = "step-editor-row";
      row.innerHTML = `
        <span class="step-editor-num"></span>
        <input type="text" name="steps" maxlength="120" required placeholder="下一步" />
        <button type="button" class="btn-ghost btn-inline" data-remove-step>删除</button>
      `;
      if (value) row.querySelector("input").value = value;
      list.appendChild(row);
      renumber(list);
    }

    if (addBtn) {
      addBtn.addEventListener("click", () => addRow(""));
    }

    list.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-remove-step]");
      if (!btn) return;
      const rows = list.querySelectorAll(".step-editor-row");
      if (rows.length <= 1) return;
      btn.closest(".step-editor-row")?.remove();
      renumber(list);
    });

    renumber(list);
  }

  // —— 创建表单步骤编辑 ——
  bindStepEditor(
    document.getElementById("steps-editor-list"),
    document.getElementById("add-step-btn")
  );

  document.querySelectorAll("[data-edit-steps]").forEach((list) => {
    const addBtn = list.parentElement?.querySelector("[data-add-step]");
    bindStepEditor(list, addBtn);
  });

  // —— 家属操作 ——
  let busy = false;

  async function familyAction(fn) {
    if (busy) return;
    busy = true;
    try {
      await fn();
      window.location.reload();
    } catch (err) {
      alert(err.message || "操作失败");
      if (err.data && err.data.conflict) window.location.reload();
    } finally {
      busy = false;
    }
  }

  document.querySelectorAll("[data-proxy-step]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const taskId = btn.getAttribute("data-proxy-step");
      const step = Number(btn.getAttribute("data-step") || 0);
      familyAction(() =>
        api(`/api/tasks/${taskId}/advance`, {
          action: "proxy",
          expected_step_index: step,
          action_id: actionId(),
        })
      );
    });
  });

  document.querySelectorAll("[data-proxy-all]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!confirm("确定代为完成整件任务？")) return;
      const taskId = btn.getAttribute("data-proxy-all");
      familyAction(() =>
        api(`/api/tasks/${taskId}/complete-all`, { action_id: actionId() })
      );
    });
  });

  document.querySelectorAll("[data-reset-today]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!confirm("重置后今天的进度会清空，确定？")) return;
      const taskId = btn.getAttribute("data-reset-today");
      familyAction(() =>
        api(`/api/tasks/${taskId}/reset`, { action_id: actionId() })
      );
    });
  });

  // —— 老人端 ——
  if (role !== "elder") return;

  const focus = document.getElementById("elder-focus");
  if (!focus) return;
  const taskId = focus.dataset.taskId;
  const stepText = document.getElementById("elder-step-text");
  const stepTitle = document.getElementById("elder-step-title");
  const progressFill = document.getElementById("elder-progress-fill");
  const progressText = document.getElementById("elder-progress-text");
  const actions = document.getElementById("elder-actions");
  let elderBusy = false;
  let currentStepIndex = Number(
    actions?.querySelector("[data-elder-done]")?.getAttribute("data-step") || 0
  );

  function speak(text) {
    if (!window.speechSynthesis || !text) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN";
    u.rate = 0.9;
    window.speechSynthesis.speak(u);
  }

  function renderRun(run) {
    if (!run) {
      window.location.reload();
      return;
    }
    currentStepIndex = Number(run.current_step_index || 0);
    if (progressFill) progressFill.style.width = `${run.progress_percent || 0}%`;
    if (progressText) {
      progressText.textContent = `${run.done_count}/${run.total_steps} · ${run.progress_percent}%`;
    }

    if (run.status === "completed") {
      if (stepTitle) stepTitle.textContent = "做完了";
      if (stepText) stepText.textContent = `「${run.title}」今天的步骤都完成了。`;
      if (actions) {
        actions.innerHTML = `<p class="welcome-desc">真棒！可以看看今天还有没有别的事。</p>`;
      }
      return;
    }

    if (run.status === "paused") {
      if (stepTitle) stepTitle.textContent = "已暂停";
      if (stepText) {
        stepText.textContent = run.current_step
          ? `停在：${run.current_step.content}`
          : "稍后再继续。";
      }
      if (actions) {
        actions.innerHTML = `<button type="button" class="btn-primary elder-btn" data-elder-resume>继续</button>`;
        bindElderButtons();
      }
      return;
    }

    if (run.status === "not_started") {
      if (stepTitle) stepTitle.textContent = "准备开始";
      if (stepText) stepText.textContent = "点「开始」后，会一步一步引导您。";
      if (actions) {
        actions.innerHTML = `<button type="button" class="btn-primary elder-btn" data-elder-start>开始</button>`;
        bindElderButtons();
      }
      return;
    }

    const cur = run.current_step;
    if (stepTitle) {
      stepTitle.textContent = `第 ${(cur?.index ?? currentStepIndex) + 1} / ${run.total_steps} 步`;
    }
    if (stepText) stepText.textContent = cur ? cur.content : "";
    if (actions) {
      actions.innerHTML = `
        <button type="button" class="btn-primary elder-btn" data-elder-done data-step="${currentStepIndex}">做好了</button>
        <button type="button" class="btn-outline elder-btn" data-elder-skip data-step="${currentStepIndex}">跳过</button>
        <button type="button" class="btn-ghost elder-btn" data-elder-pause>先不做了</button>
        <button type="button" class="btn-primary elder-btn" data-elder-complete-all>整件做完</button>
        <button type="button" class="btn-ghost elder-btn" data-elder-speak>再说一遍</button>
      `;
      bindElderButtons();
    }
  }

  async function elderCall(fn) {
    if (elderBusy || !taskId) return;
    elderBusy = true;
    actions?.querySelectorAll("button").forEach((b) => {
      b.disabled = true;
    });
    try {
      const data = await fn();
      renderRun(data.run);
    } catch (err) {
      alert(err.message || "请稍后再试");
      if (err.data && err.data.run) renderRun(err.data.run);
      else if (err.data && err.data.conflict) window.location.reload();
    } finally {
      elderBusy = false;
      actions?.querySelectorAll("button").forEach((b) => {
        b.disabled = false;
      });
    }
  }

  function bindElderButtons() {
    actions?.querySelector("[data-elder-start]")?.addEventListener("click", () => {
      elderCall(() =>
        api(`/api/tasks/${taskId}/start`, { action_id: actionId() })
      );
    });
    actions?.querySelector("[data-elder-resume]")?.addEventListener("click", () => {
      elderCall(() =>
        api(`/api/tasks/${taskId}/resume`, { action_id: actionId() })
      );
    });
    actions?.querySelector("[data-elder-pause]")?.addEventListener("click", () => {
      elderCall(() =>
        api(`/api/tasks/${taskId}/pause`, { action_id: actionId() })
      );
    });
    actions?.querySelector("[data-elder-done]")?.addEventListener("click", () => {
      const step = Number(
        actions.querySelector("[data-elder-done]")?.getAttribute("data-step") || currentStepIndex
      );
      elderCall(() =>
        api(`/api/tasks/${taskId}/advance`, {
          action: "done",
          expected_step_index: step,
          action_id: actionId(),
        })
      );
    });
    actions?.querySelector("[data-elder-skip]")?.addEventListener("click", () => {
      const step = Number(
        actions.querySelector("[data-elder-skip]")?.getAttribute("data-step") || currentStepIndex
      );
      elderCall(() =>
        api(`/api/tasks/${taskId}/advance`, {
          action: "skip",
          expected_step_index: step,
          action_id: actionId(),
        })
      );
    });
    actions?.querySelector("[data-elder-complete-all]")?.addEventListener("click", () => {
      if (!confirm("确定把这件事的全部步骤都标记为完成？")) return;
      elderCall(() =>
        api(`/api/tasks/${taskId}/complete-all`, { action_id: actionId() })
      );
    });
    actions?.querySelector("[data-elder-speak]")?.addEventListener("click", () => {
      speak(stepText?.textContent || "");
    });
  }

  if (taskId) bindElderButtons();
})();
