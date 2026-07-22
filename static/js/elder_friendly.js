/**
 * 适老化朗读：为带 data-speak-card 的卡片提供「大声朗读」
 * 语速偏慢，适合老年用户。
 */
(() => {
  "use strict";

  function collectText(card) {
    const dedicated = card.querySelector("[data-speak-text]");
    if (dedicated) return dedicated.innerText.trim();
    const clone = card.cloneNode(true);
    clone.querySelectorAll(".speak-btn, button, a.btn-primary, a.btn-outline, a.btn-ghost").forEach((el) => el.remove());
    return clone.innerText.replace(/\s+/g, " ").trim();
  }

  function stopAll() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    document.querySelectorAll(".speak-btn.is-speaking").forEach((btn) => {
      btn.classList.remove("is-speaking");
      btn.textContent = "🔊 大声朗读";
    });
  }

  function speak(text, btn) {
    if (!window.speechSynthesis) {
      alert("当前浏览器暂不支持朗读。");
      return;
    }
    stopAll();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN";
    u.rate = 0.78;
    u.pitch = 1;
    u.volume = 1;
    if (btn) {
      btn.classList.add("is-speaking");
      btn.textContent = "⏹ 停止朗读";
    }
    u.onend = u.onerror = () => {
      if (btn) {
        btn.classList.remove("is-speaking");
        btn.textContent = "🔊 大声朗读";
      }
    };
    window.speechSynthesis.speak(u);
  }

  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".speak-btn");
    if (!btn) return;
    if (btn.classList.contains("is-speaking")) {
      stopAll();
      return;
    }
    const card = btn.closest("[data-speak-card]");
    if (!card) return;
    const text = collectText(card);
    if (!text) return;
    speak(text, btn);
  });
})();
