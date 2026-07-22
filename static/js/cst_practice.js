/**
 * CST 训练题目 · 语音播报 + 录音识别 + 点选作答
 */
(() => {
  const root = document.getElementById("cst-live-practice");
  if (!root) return;

  const Speech = window.SpeechService;
  const sessionNum = root.dataset.sessionNum;
  const role = root.dataset.role || "elder";
  const listEl = document.getElementById("live-practice-list");
  const detailsEl = document.getElementById("practice-all-details");
  const statusEl = document.getElementById("practice-status");
  const progressFill = document.getElementById("practice-progress-fill");
  const progressText = document.getElementById("practice-progress-text");
  const generateBtn = document.getElementById("btn-generate-practice");

  const focusEl = document.getElementById("voice-focus");
  const focusMedia = document.getElementById("voice-focus-media");
  const focusIndex = document.getElementById("voice-focus-index");
  const focusPrompt = document.getElementById("voice-focus-prompt");
  const focusHint = document.getElementById("voice-focus-hint");
  const focusOptions = document.getElementById("voice-focus-options");
  const asrTextEl = document.getElementById("voice-asr-text");
  const feedbackEl = document.getElementById("voice-feedback");

  const btnSpeak = document.getElementById("btn-speak-question");
  const btnRepeat = document.getElementById("btn-repeat-question");
  const btnRecord = document.getElementById("btn-record-toggle");
  const btnRerecord = document.getElementById("btn-rerecord");
  const btnNext = document.getElementById("btn-next-question");
  const spdInput = document.getElementById("speech-spd");
  const spdLabel = document.getElementById("speech-spd-label");
  const perSelect = document.getElementById("speech-per");

  let runId = root.dataset.runId || "";
  let questions = [];
  let answeredIds = new Set();
  let currentIndex = 0;
  let busy = false;
  let recording = false;
  let autoAdvanceTimer = null;

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text || "";
  }

  function currentQuestion() {
    return questions[currentIndex] || null;
  }

  function updateProgress() {
    const total = questions.length;
    const answered = answeredIds.size;
    const percent = total ? Math.round((100 * answered) / total) : 0;
    if (progressFill) progressFill.style.width = `${percent}%`;
    if (progressText) {
      progressText.textContent = total
        ? `${answered}/${total} · 第 ${Math.min(currentIndex + 1, total)} 题`
        : (role === "family" ? "生成后开始" : "等待出题");
    }
  }

  function renderFocus() {
    const q = currentQuestion();
    if (!focusEl) return;
    if (!q) {
      focusEl.hidden = true;
      if (detailsEl) detailsEl.hidden = true;
      return;
    }
    focusEl.hidden = false;
    if (detailsEl) detailsEl.hidden = false;

    if (focusIndex) {
      focusIndex.textContent = `第 ${currentIndex + 1} / ${questions.length} 题`;
    }
    if (focusPrompt) focusPrompt.textContent = q.prompt || "";
    if (focusHint) focusHint.textContent = q.hint || "慢慢想，没有对错。";

    if (focusMedia) {
      if (q.image_url) {
        focusMedia.innerHTML = `<img src="${escapeHtml(q.image_url)}" alt="${escapeHtml(
          q.material_title || q.visual_label || "题目图片"
        )}" />`;
      } else {
        focusMedia.innerHTML = `<div class="live-practice-fallback" style="--tone:${escapeHtml(
          q.visual_tone || "#0f766e"
        )};min-height:160px;border-radius:12px;">
          <span>${escapeHtml(q.visual_emoji || "💬")}</span>
        </div>`;
      }
    }

    if (focusOptions) {
      focusOptions.innerHTML = (q.options || [])
        .map(
          (opt) =>
            `<button type="button" class="option-chip practice-live-option" data-answer="${escapeHtml(
              opt
            )}">${escapeHtml(opt)}</button>`
        )
        .join("");
    }

    if (asrTextEl) asrTextEl.textContent = "（尚未录音）";
    if (feedbackEl) {
      feedbackEl.textContent = answeredIds.has(q.id)
        ? "本题已作答，可点「下一题」或重新录音。"
        : "请先听题目，再录音或点选回答。";
    }
    if (btnRerecord) btnRerecord.hidden = true;
    updateProgress();
  }

  function renderList() {
    if (!listEl) return;
    listEl.innerHTML = questions
      .map((q, index) => {
        const tone = escapeHtml(q.visual_tone || "#0f766e");
        const media = q.image_url
          ? `<img src="${escapeHtml(q.image_url)}" alt="" loading="lazy" />`
          : `<div class="live-practice-fallback" aria-hidden="true">
               <span class="live-practice-emoji">${escapeHtml(q.visual_emoji || "💬")}</span>
               <strong>${escapeHtml(q.visual_label || "练习画面")}</strong>
             </div>`;
        const done = answeredIds.has(q.id) ? "is-answered" : "";
        const options = (q.options || [])
          .map(
            (opt) =>
              `<button type="button" class="option-chip practice-live-option" data-answer="${escapeHtml(
                opt
              )}">${escapeHtml(opt)}</button>`
          )
          .join("");
        return `<article class="live-practice-card ${done}" data-qid="${escapeHtml(
          q.id
        )}" data-index="${index}" style="--tone:${tone}">
          <div class="live-practice-media">${media}</div>
          <div class="live-practice-body">
            <div class="quiz-head"><span class="quiz-index">第 ${index + 1} 题</span></div>
            <p class="quiz-prompt">${escapeHtml(q.prompt)}</p>
            <div class="quiz-options">${options}</div>
            <p class="practice-feedback" data-q-feedback hidden></p>
          </div>
        </article>`;
      })
      .join("");
  }

  function applyRun(run) {
    questions = run.questions || [];
    runId = String(run.id || run.run_id || "");
    root.dataset.runId = runId;
    answeredIds = new Set(run.answered_ids || (run.answers || []).map((a) => a.question_id));
    // 定位到第一道未答题
    currentIndex = Math.max(
      0,
      questions.findIndex((q) => !answeredIds.has(q.id))
    );
    if (currentIndex < 0) currentIndex = 0;
    renderFocus();
    renderList();
    if (generateBtn) generateBtn.textContent = "换一批题";
  }

  async function saveAnswerText(text) {
    if (!runId) throw new Error("请先生成题目");
    const q = currentQuestion();
    if (!q) throw new Error("没有当前题目");
    const resp = await fetch(`/api/cst/practice/${sessionNum}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: Number(runId),
        question_id: q.id,
        answer_text: text,
      }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) throw new Error(data.error || "保存失败");
    answeredIds.add(q.id);
    if (data.run) {
      answeredIds = new Set((data.run.answers || []).map((a) => a.question_id));
    }
    updateProgress();
    renderList();
    return data;
  }

  async function speakQuestion(auto = false) {
    const q = currentQuestion();
    if (!q || !Speech) return;
    if (busy) return;
    busy = true;
    setStatus(auto ? "正在播报题目…" : "正在重新播报…");
    try {
      const line = q.hint ? `${q.prompt}。${q.hint}` : q.prompt;
      await Speech.synthesizeSpeech(line, { cue: true });
      setStatus("请语音回答，或点选下方选项");
    } catch (err) {
      setStatus(err.message || "播报失败，请阅读题目文字");
    } finally {
      busy = false;
    }
  }

  async function handleRecognizedText(text) {
    const q = currentQuestion();
    if (!q) return;
    if (asrTextEl) asrTextEl.textContent = text || "（未识别到内容）";
    if (!text) {
      if (feedbackEl) feedbackEl.textContent = "没有听清，请点「重新录音」。";
      if (btnRerecord) btnRerecord.hidden = false;
      setStatus("识别为空，可重新录音");
      return;
    }

    let evalResult = {
      message: `已记下「${text}」`,
      speak: "很好，我们继续下一题。",
    };
    try {
      evalResult = await Speech.evaluateAnswer(text, q);
    } catch (_err) {
      /* 降级：仅保存 */
    }
    if (feedbackEl) feedbackEl.textContent = evalResult.message || "很好。";
    await saveAnswerText(text);
    setStatus("回答已保存");
    if (btnRerecord) btnRerecord.hidden = false;

    try {
      await Speech.synthesizeSpeech(evalResult.speak || "很好，我们继续。", { cue: true });
    } catch (_err) {
      /* ignore */
    }

    // 自动下一题
    clearTimeout(autoAdvanceTimer);
    autoAdvanceTimer = setTimeout(() => {
      goNext(true);
    }, 600);
  }

  async function toggleRecord() {
    if (!Speech) {
      setStatus("语音模块未加载");
      return;
    }
    if (busy && !recording) return;

    if (!recording) {
      try {
        busy = true;
        setStatus("正在打开麦克风…");
        await Speech.startRecording();
        recording = true;
        if (btnRecord) {
          btnRecord.textContent = "停止";
          btnRecord.classList.add("is-recording");
        }
        setStatus("录音中…说完再点停止");
      } catch (err) {
        setStatus(err.message || "无法录音");
      } finally {
        busy = false;
      }
      return;
    }

    // stop
    busy = true;
    if (btnRecord) {
      btnRecord.textContent = "识别中…";
      btnRecord.disabled = true;
    }
    setStatus("正在识别语音…");
    try {
      const blob = await Speech.stopRecording();
      recording = false;
      const text = await Speech.recognizeSpeech(blob);
      await handleRecognizedText(text);
    } catch (err) {
      setStatus(err.message || "识别失败，可点选选项作答");
      if (feedbackEl) feedbackEl.textContent = err.message || "识别失败";
      if (btnRerecord) btnRerecord.hidden = false;
    } finally {
      recording = false;
      busy = false;
      if (btnRecord) {
        btnRecord.disabled = false;
        btnRecord.textContent = "录音回答";
        btnRecord.classList.remove("is-recording");
      }
    }
  }

  async function goNext(autoSpeak) {
    if (!questions.length) return;
    if (currentIndex < questions.length - 1) {
      currentIndex += 1;
    } else {
      // 找未答
      const nextUnanswered = questions.findIndex((q) => !answeredIds.has(q.id));
      if (nextUnanswered >= 0) currentIndex = nextUnanswered;
      else setStatus("全部题目已完成，真棒！");
    }
    renderFocus();
    if (autoSpeak) await speakQuestion(true);
  }

  async function generate() {
    if (busy || role !== "family") return;
    busy = true;
    if (generateBtn) generateBtn.disabled = true;
    setStatus("正在结合上传资料，由 DeepSeek 随机生成题目…");
    try {
      const resp = await fetch(`/api/cst/practice/${sessionNum}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count: 10 }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || "生成失败");
      applyRun({
        id: data.run_id,
        questions: data.questions,
        answered_ids: [],
        answers: [],
      });
      setStatus(
        data.used_deepseek
          ? `已生成 ${data.question_count} 题（DeepSeek）`
          : `已生成 ${data.question_count} 题（本地题库）`
      );
      await speakQuestion(true);
    } catch (err) {
      setStatus(err.message || "生成失败");
    } finally {
      busy = false;
      if (generateBtn) generateBtn.disabled = false;
    }
  }

  // —— 事件绑定 ——
  if (generateBtn) generateBtn.addEventListener("click", generate);
  if (btnSpeak) btnSpeak.addEventListener("click", () => speakQuestion(false));
  if (btnRepeat) btnRepeat.addEventListener("click", () => speakQuestion(false));
  if (btnRecord) btnRecord.addEventListener("click", toggleRecord);
  if (btnRerecord) {
    btnRerecord.addEventListener("click", async () => {
      if (asrTextEl) asrTextEl.textContent = "（尚未录音）";
      if (feedbackEl) feedbackEl.textContent = "请重新录音回答。";
      await toggleRecord();
    });
  }
  if (btnNext) btnNext.addEventListener("click", () => goNext(true));

  if (spdInput) {
    spdInput.addEventListener("input", () => {
      const v = Number(spdInput.value || 4);
      if (spdLabel) spdLabel.textContent = String(v);
      if (Speech) Speech.setSpeed(v);
    });
  }
  if (perSelect) {
    perSelect.addEventListener("change", () => {
      if (Speech) Speech.setVoice(Number(perSelect.value || 0));
    });
  }

  // 点选作答（焦点区 + 列表）
  root.addEventListener("click", async (event) => {
    const btn = event.target.closest(".practice-live-option");
    if (!btn || busy) return;
    const card = btn.closest(".live-practice-card");
    if (card && card.dataset.index != null) {
      currentIndex = Number(card.dataset.index) || currentIndex;
      renderFocus();
    }
    const text = btn.dataset.answer || btn.textContent.trim();
    busy = true;
    setStatus("正在保存回答…");
    try {
      if (asrTextEl) asrTextEl.textContent = text;
      let evalResult = { message: `已选择「${text}」`, speak: "很好，我们继续。" };
      if (Speech) {
        try {
          evalResult = await Speech.evaluateAnswer(text, currentQuestion() || {});
        } catch (_err) {
          /* ignore */
        }
      }
      if (feedbackEl) feedbackEl.textContent = evalResult.message;
      await saveAnswerText(text);
      if (Speech) {
        try {
          await Speech.synthesizeSpeech(evalResult.speak || "很好。", { cue: true });
        } catch (_err) {
          /* ignore */
        }
      }
      clearTimeout(autoAdvanceTimer);
      autoAdvanceTimer = setTimeout(() => goNext(true), 500);
    } catch (err) {
      setStatus(err.message || "保存失败");
    } finally {
      busy = false;
    }
  });

  // 初始化：从页面已有列表解析题目，或保持空
  async function boot() {
    if (Speech) {
      const cfg = await Speech.loadConfig();
      if (spdInput && cfg.default_spd != null) {
        spdInput.value = String(cfg.default_spd);
        if (spdLabel) spdLabel.textContent = String(cfg.default_spd);
        Speech.setSpeed(cfg.default_spd);
      }
      if (perSelect && cfg.default_per != null) {
        perSelect.value = String(cfg.default_per);
        Speech.setVoice(cfg.default_per);
      }
      if (!cfg.configured) {
        setStatus("未配置百度语音时，将使用浏览器朗读；录音识别需配置百度凭证。");
      }
    }

    // 从 DOM 卡片恢复 questions（服务端已渲染）
    if (listEl) {
      const cards = Array.from(listEl.querySelectorAll(".live-practice-card"));
      if (cards.length) {
        questions = cards.map((card) => {
          const opts = Array.from(card.querySelectorAll(".practice-live-option")).map((b) =>
            b.dataset.answer || b.textContent.trim()
          );
          const img = card.querySelector(".live-practice-media img");
          return {
            id: card.dataset.qid,
            prompt: (card.querySelector(".quiz-prompt") || {}).textContent || "",
            hint: (card.querySelector(".quiz-ref") || {}).textContent || "",
            options: opts,
            image_url: img ? img.getAttribute("src") : "",
            visual_emoji: "💬",
            visual_label: "练习画面",
            visual_tone: "#0f766e",
          };
        });
        answeredIds = new Set(
          cards.filter((c) => c.classList.contains("is-answered")).map((c) => c.dataset.qid)
        );
        currentIndex = Math.max(
          0,
          questions.findIndex((q) => !answeredIds.has(q.id))
        );
        if (currentIndex < 0) currentIndex = 0;
        renderFocus();
      }
    }
  }

  boot();
})();
