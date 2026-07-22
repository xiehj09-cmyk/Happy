(function () {
  "use strict";

  function initWordCloud() {
    var cloud = document.querySelector(".word-cloud");
    var hint = document.getElementById("word-cloud-hint");
    if (!cloud) return;

    cloud.addEventListener("click", function (event) {
      var chip = event.target.closest(".word-chip");
      if (!chip) return;

      cloud.querySelectorAll(".word-chip.is-picked").forEach(function (el) {
        el.classList.remove("is-picked");
      });
      chip.classList.add("is-picked");

      if (hint) {
        hint.hidden = false;
        hint.textContent = "您选了「" + chip.dataset.word + "」——很好，可以说说它让您想起什么。";
      }
    });
  }

  function initClassifyGame() {
    var root = document.querySelector("[data-classify-root]");
    if (!root) return;

    var selected = null;
    var placements = {};
    var pool = root.querySelector("[data-classify-pool]");
    var feedback = root.querySelector("[data-classify-feedback]");
    var successHint = root.dataset.success || "分得好！";
    var items = Array.prototype.slice.call(root.querySelectorAll(".classify-item"));
    var bins = Array.prototype.slice.call(root.querySelectorAll(".classify-bin"));

    function renderBins() {
      bins.forEach(function (bin) {
        var list = bin.querySelector("[data-bin-items]");
        if (!list) return;
        list.innerHTML = "";
        Object.keys(placements).forEach(function (itemId) {
          if (placements[itemId] !== bin.dataset.bin) return;
          var source = root.querySelector('.classify-item[data-item-id="' + itemId + '"]');
          if (!source) return;
          var li = document.createElement("li");
          li.textContent = source.textContent.trim();
          list.appendChild(li);
        });
      });
    }

    function checkComplete() {
      if (!feedback) return;
      var allPlaced = items.every(function (item) {
        return placements[item.dataset.itemId];
      });
      if (!allPlaced) {
        feedback.textContent = "继续点选物品，再点篮子。";
        feedback.classList.remove("is-ok");
        return;
      }
      var allCorrect = items.every(function (item) {
        return placements[item.dataset.itemId] === item.dataset.correctBin;
      });
      if (allCorrect) {
        feedback.textContent = successHint;
        feedback.classList.add("is-ok");
      } else {
        feedback.textContent = "有几样可以再想想，点篮子外的物品可重新分。";
        feedback.classList.remove("is-ok");
      }
    }

    items.forEach(function (item) {
      item.addEventListener("click", function () {
        if (item.classList.contains("is-placed")) {
          delete placements[item.dataset.itemId];
          item.classList.remove("is-placed");
          item.classList.remove("is-selected");
          selected = null;
          bins.forEach(function (bin) {
            bin.classList.remove("is-target");
          });
          renderBins();
          if (feedback) {
            feedback.textContent = "已取回「" + item.textContent.trim() + "」，可重新分类。";
            feedback.classList.remove("is-ok");
          }
          return;
        }
        items.forEach(function (el) {
          el.classList.remove("is-selected");
        });
        item.classList.add("is-selected");
        selected = item;
        bins.forEach(function (bin) {
          bin.classList.add("is-target");
        });
        if (feedback) {
          feedback.textContent = "已选「" + item.textContent.trim() + "」，请点一个篮子。";
          feedback.classList.remove("is-ok");
        }
      });
    });

    bins.forEach(function (bin) {
      bin.addEventListener("click", function () {
        if (!selected) {
          if (feedback) {
            feedback.textContent = "请先点选下方的一个物品。";
            feedback.classList.remove("is-ok");
          }
          return;
        }
        placements[selected.dataset.itemId] = bin.dataset.bin;
        selected.classList.add("is-placed");
        selected.classList.remove("is-selected");
        selected = null;
        bins.forEach(function (el) {
          el.classList.remove("is-target");
        });
        renderBins();
        checkComplete();
      });
    });
  }

  function initCurriculumPractice() {
    var root = document.getElementById("cst-curriculum-practice");
    if (!root) return;
    var sessionNum = root.dataset.sessionNum;
    var statusEl = document.getElementById("curriculum-status");
    var busy = false;
    var recordingItem = null;
    var Speech = window.SpeechService;

    function setStatus(msg) {
      if (statusEl) statusEl.textContent = msg || "";
    }

    function speakText(text) {
      if (Speech && Speech.synthesizeSpeech) {
        return Speech.loadConfig().then(function () {
          Speech.setSpeed(4);
          return Speech.synthesizeSpeech(text, { spd: 4, per: 0, cue: true });
        });
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        var u = new SpeechSynthesisUtterance(text);
        u.lang = "zh-CN";
        u.rate = 0.85;
        window.speechSynthesis.speak(u);
      }
      return Promise.resolve();
    }

    function handleSpeak(btn, item) {
      var textEl = btn.querySelector("[data-card-speak-text]");
      if (!textEl) return;
      busy = true;
      btn.disabled = true;
      btn.classList.add("is-speaking");
      var cached = (btn.dataset.speakText || "").trim();
      var original = textEl.textContent;
      textEl.textContent = cached ? "正在播报…" : "准备中…";
      setStatus(cached ? "正在播报…" : "正在生成温柔短句…");

      var ready = cached
        ? Promise.resolve({ text: cached, source: "cache" })
        : fetch("/api/cst/session/" + sessionNum + "/card-speak", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              card_id: item.dataset.curriculumId || "",
              label: item.dataset.label || "",
              caption: item.dataset.caption || "",
              ai_prompt: item.dataset.aiPrompt || item.dataset.prompt || "",
              prompt: item.dataset.prompt || "",
            }),
          }).then(function (resp) {
            return resp.json().then(function (data) {
              if (!resp.ok || !data.ok) {
                throw new Error((data && data.error) || "生成失败");
              }
              return data;
            });
          });

      ready
        .then(function (data) {
          var text = (data.text || "").trim();
          btn.dataset.speakText = text;
          textEl.textContent = text;
          setStatus("正在播报…");
          return speakText(text);
        })
        .then(function () {
          setStatus("播报完成，可以录音说说您想到的");
        })
        .catch(function (err) {
          setStatus((err && err.message) || "暂时无法播报");
          textEl.textContent = btn.dataset.speakText || original || item.dataset.prompt || "点我听题";
        })
        .finally(function () {
          busy = false;
          btn.disabled = false;
          btn.classList.remove("is-speaking");
          if (btn.dataset.speakText) textEl.textContent = btn.dataset.speakText;
        });
    }

    function stopRecordUi(item) {
      var recordBtn = item && item.querySelector(".curriculum-record-btn");
      if (recordBtn) {
        recordBtn.classList.remove("is-recording");
        recordBtn.textContent = "录音回答";
        recordBtn.disabled = false;
      }
      recordingItem = null;
    }

    function handleRecord(item) {
      if (!Speech || !Speech.startRecording) {
        setStatus("当前浏览器暂不支持录音");
        return;
      }
      var recordBtn = item.querySelector(".curriculum-record-btn");
      var asrEl = item.querySelector("[data-curriculum-asr]");
      var fbEl = item.querySelector("[data-curriculum-feedback]");

      if (recordingItem === item) {
        busy = true;
        if (recordBtn) {
          recordBtn.disabled = true;
          recordBtn.textContent = "识别中…";
        }
        setStatus("正在识别您说的话…");
        Speech.stopRecording()
          .then(function (blob) {
            return Speech.recognizeSpeech(blob);
          })
          .then(function (text) {
            var said = (text || "").trim();
            if (asrEl) {
              asrEl.hidden = false;
              asrEl.textContent = said ? "您说：" + said : "没有听清，请再试一次";
            }
            if (!said) throw new Error("没有听清，请再说一遍");
            setStatus("正在温柔回应…");
            if (fbEl) {
              fbEl.hidden = false;
              fbEl.textContent = "正在想一想怎么接话…";
            }
            return fetch("/api/cst/session/" + sessionNum + "/practice-reply", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                prompt: item.dataset.prompt || "",
                hint: item.dataset.hint || "",
                transcript: said,
              }),
            }).then(function (resp) {
              return resp.json().then(function (data) {
                if (!resp.ok || !data.ok) {
                  throw new Error((data && data.error) || "回复失败");
                }
                return data;
              });
            });
          })
          .then(function (data) {
            var reply = (data.reply || "").trim();
            if (fbEl) {
              fbEl.hidden = false;
              fbEl.textContent = reply;
            }
            setStatus("正在播报回应…");
            return speakText(reply).then(function () {
              return reply;
            });
          })
          .then(function () {
            setStatus("可以说得更多，也可以做下一题");
          })
          .catch(function (err) {
            setStatus((err && err.message) || "录音回答失败");
            if (fbEl) {
              fbEl.hidden = false;
              if (!fbEl.textContent || fbEl.textContent.indexOf("正在想") === 0) {
                fbEl.textContent = (err && err.message) || "请再试一次";
              }
            }
          })
          .finally(function () {
            busy = false;
            stopRecordUi(item);
          });
        return;
      }

      if (recordingItem && recordingItem !== item) {
        setStatus("请先结束上一题的录音");
        return;
      }

      busy = true;
      setStatus("请开始说话…");
      if (recordBtn) {
        recordBtn.classList.add("is-recording");
        recordBtn.textContent = "点击结束";
      }
      if (asrEl) {
        asrEl.hidden = false;
        asrEl.textContent = "正在听您说…";
      }
      if (fbEl) {
        fbEl.hidden = true;
        fbEl.textContent = "";
      }

      Speech.loadConfig()
        .then(function () {
          return Speech.startRecording();
        })
        .then(function () {
          recordingItem = item;
          busy = false;
        })
        .catch(function (err) {
          busy = false;
          stopRecordUi(item);
          setStatus((err && err.message) || "无法开始录音");
        });
    }

    root.addEventListener("click", function (event) {
      var speakBtn = event.target.closest(".curriculum-speak-btn");
      if (speakBtn) {
        if (busy || recordingItem) return;
        var speakItem = speakBtn.closest(".curriculum-item");
        if (speakItem) handleSpeak(speakBtn, speakItem);
        return;
      }

      var recordBtn = event.target.closest(".curriculum-record-btn");
      if (recordBtn) {
        if (busy && recordingItem !== recordBtn.closest(".curriculum-item")) return;
        var recordItem = recordBtn.closest(".curriculum-item");
        if (recordItem) handleRecord(recordItem);
      }
    });
  }

  initWordCloud();
  initClassifyGame();
  initCurriculumPractice();
})();
