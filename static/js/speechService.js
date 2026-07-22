/**
 * 百度语音前端服务（经本站后端代理，密钥不落浏览器）
 * - synthesizeSpeech: TTS 播报（AD 关怀：情感音色 / 慢语速 / Web Audio 淡入淡出）
 * - startRecording / stopRecording: MediaRecorder + 转 16kHz WAV
 * - recognizeSpeech: 上传 WAV 识别
 */
(() => {
  "use strict";

  // —— AD 认知训练 TTS 配置（慢速、情感女声优先，便于听力与理解）——
  /** 语速 0–15；3=较慢、吐字清晰，适合认知障碍患者 */
  const TTS_SPEAK_RATE = 3;
  /** 音调 0–15；略高于默认 5，更温暖亲和 */
  const TTS_PITCH = 6;
  /** 音量 0–15；略大，便于听力衰退的老年用户 */
  const TTS_VOLUME = 10;
  /** aue=3 → MP3，情感表现更饱满；失败时可降级由服务端处理 */
  const TTS_AUE = 3;
  /**
   * 发音人优先队列：
   * 4=度丫丫(情感女声) → 3=度逍遥(情感男声) → 5=度博文 → 6=度小童
   */
  const TTS_VOICE_PREFERENCE = [4, 3, 5, 6];
  /** Web Audio 播放峰值增益（百度 vol 已抬高；此处控制淡入淡出） */
  const TTS_PLAYBACK_GAIN = 1.05;
  const TTS_FADE_SEC = 0.09;

  const SpeechService = {
    _config: null,
    _audioEl: null,
    _playbackCtx: null,
    _playbackSource: null,
    _playbackGain: null,
    _mediaStream: null,
    _mediaRecorder: null,
    _chunks: [],
    _audioCtx: null,
    _processor: null,
    _source: null,
    _pcmChunks: [],
    _recording: false,
    _spd: TTS_SPEAK_RATE,
    _per: TTS_VOICE_PREFERENCE[0],

    /** 拉取服务端公开配置（是否已配置百度、默认语速/音色） */
    async loadConfig() {
      try {
        const resp = await fetch("/api/speech/config");
        const data = await resp.json();
        this._config = data;
        // 配置仅作参考；synthesizeSpeech 仍以 AD 关怀常量为主
        if (typeof data.default_spd === "number") this._spd = data.default_spd;
        if (typeof data.default_per === "number") this._per = data.default_per;
        return data;
      } catch (_err) {
        this._config = { configured: false };
        return this._config;
      }
    },

    isConfigured() {
      return !!(this._config && this._config.configured);
    },

    setSpeed(spd) {
      this._spd = Math.max(0, Math.min(15, Number(spd) || TTS_SPEAK_RATE));
    },

    setVoice(per) {
      this._per = Number(per) || TTS_VOICE_PREFERENCE[0];
    },

    getSpeed() {
      return this._spd;
    },

    getVoice() {
      return this._per;
    },

    /**
     * 文本润色：在句读后插入停顿感，让百度 TTS 朗读更有节奏（非机器连读）。
     * 利用空格 / 逗号延长句间气口，适合护理式温柔播报。
     */
    _polishTtsText(text) {
      let t = String(text || "").trim();
      if (!t) return "";
      // 句末强停顿 → 逗号 + 空格，模拟换气
      t = t.replace(/([。！？；])/g, "$1， ");
      // 顿号/逗号后补空格，避免粘连
      t = t.replace(/([，、])/g, "$1 ");
      // 省略号略作停顿
      t = t.replace(/…+/g, "…， ");
      t = t.replace(/\.{3,}/g, "…， ");
      t = t.replace(/\s{2,}/g, " ");
      return t.trim();
    },

    /** 短提示音，帮助注意力聚焦 */
    async playCue(kind = "start") {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = kind === "end" ? 660 : 520;
        gain.gain.value = 0.05;
        osc.start();
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
        osc.stop(ctx.currentTime + 0.2);
        await new Promise((r) => setTimeout(r, 220));
        ctx.close();
      } catch (_err) {
        /* 忽略提示音失败 */
      }
    },

    stopPlayback() {
      // 停止 Web Audio 播报源（与录音用的 _audioCtx 分离，避免互相干扰）
      if (this._playbackSource) {
        try {
          this._playbackSource.onended = null;
          this._playbackSource.stop(0);
        } catch (_err) {
          /* already stopped */
        }
        this._playbackSource = null;
      }
      this._playbackGain = null;
      if (this._audioEl) {
        try {
          this._audioEl.pause();
          this._audioEl.removeAttribute("src");
          this._audioEl.load();
        } catch (_err) {
          /* ignore */
        }
      }
    },

    /**
     * 用 Web Audio API 播放 TTS 音频（支持 MP3 decodeAudioData），淡入淡出避免切入突兀。
     * @param {Blob} blob
     */
    async _playTtsBlob(blob) {
      this.stopPlayback();
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) {
        // 极旧环境降级：HTMLAudioElement
        const url = URL.createObjectURL(blob);
        if (!this._audioEl) this._audioEl = new Audio();
        this._audioEl.src = url;
        await this._audioEl.play();
        await new Promise((resolve, reject) => {
          this._audioEl.onended = () => {
            URL.revokeObjectURL(url);
            resolve();
          };
          this._audioEl.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("音频播放失败"));
          };
        });
        return;
      }

      if (!this._playbackCtx || this._playbackCtx.state === "closed") {
        this._playbackCtx = new AudioCtx();
      }
      if (this._playbackCtx.state === "suspended") {
        await this._playbackCtx.resume();
      }

      const arrayBuf = await blob.arrayBuffer();
      // slice 拷贝，避免部分浏览器 decodeAudioData 抽离 ArrayBuffer 后报错
      const audioBuf = await this._playbackCtx.decodeAudioData(arrayBuf.slice(0));
      const source = this._playbackCtx.createBufferSource();
      const gain = this._playbackCtx.createGain();
      source.buffer = audioBuf;
      source.connect(gain);
      gain.connect(this._playbackCtx.destination);

      const now = this._playbackCtx.currentTime;
      const fade = TTS_FADE_SEC;
      const peak = TTS_PLAYBACK_GAIN;
      const dur = Math.max(audioBuf.duration || 0, fade * 2 + 0.05);
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(peak, now + fade);
      const fadeOutAt = now + dur - fade;
      gain.gain.setValueAtTime(peak, Math.max(now + fade, fadeOutAt));
      gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);

      this._playbackSource = source;
      this._playbackGain = gain;

      await new Promise((resolve, reject) => {
        source.onended = () => resolve();
        try {
          source.start(0);
        } catch (err) {
          reject(err);
        }
      });
    },

    /**
     * 文本转语音并播放（AD 关怀音色优化）
     * 目标参数对齐百度 text2audio：spd=3, pit=6, vol=10, per=4, aue=3
     * @param {string} text
     * @param {{spd?: number, per?: number, cue?: boolean, forceSpd?: number, forcePer?: number}} options
     *        forceSpd / forcePer 可强制覆盖 AD 默认；普通 spd/per 不会压过情感慢速配置
     */
    async synthesizeSpeech(text, options = {}) {
      const raw = String(text || "").trim();
      if (!raw) throw new Error("没有可播报的内容");
      // 标点处插入气口，朗读更有抑扬顿挫
      const content = this._polishTtsText(raw);
      if (!content) throw new Error("没有可播报的内容");

      if (options.cue !== false) await this.playCue("start");

      // 认知训练默认慢速；仅 forceSpd 可完全覆盖
      const spd =
        options.forceSpd != null
          ? Math.max(0, Math.min(15, Number(options.forceSpd)))
          : TTS_SPEAK_RATE;
      const pit = TTS_PITCH;
      const vol = TTS_VOLUME;
      const aue = TTS_AUE;

      // 优先情感女声 per=4，失败再降级情感男声 / 标准音库
      const voices =
        options.forcePer != null
          ? [Number(options.forcePer)]
          : TTS_VOICE_PREFERENCE.slice();

      let lastError = null;
      for (let v = 0; v < voices.length; v += 1) {
        const per = voices[v];
        // 保留原有「同音色重试 2 次」机制（应对瞬时网络 / token 问题）
        for (let attempt = 0; attempt < 2; attempt += 1) {
          try {
            const resp = await fetch("/api/speech/tts", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                text: content,
                spd,
                per,
                pit,
                vol,
                aue,
              }),
            });
            const type = resp.headers.get("Content-Type") || "";
            if (!resp.ok || type.includes("application/json")) {
              const err = await resp.json().catch(() => ({}));
              throw new Error(err.error || "语音播报失败");
            }
            const blob = await resp.blob();
            // MP3（aue=3）经 decodeAudioData 解码后 Web Audio 播放
            await this._playTtsBlob(blob);
            if (options.cue !== false) await this.playCue("end");
            this._spd = spd;
            this._per = per;
            return true;
          } catch (err) {
            lastError = err;
            await new Promise((r) => setTimeout(r, 400));
          }
        }
      }
      // 降级：浏览器本地朗读（同样偏慢、偏柔）
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(content);
        u.lang = "zh-CN";
        u.rate = Math.max(0.55, Math.min(0.95, 0.5 + spd * 0.05));
        u.pitch = 1.05;
        window.speechSynthesis.speak(u);
        return false;
      }
      throw lastError || new Error("播报失败");
    },

    /** 将 Float32Array PCM 编码为 16kHz 16bit 单声道 WAV */
    _encodeWav(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);
      const writeStr = (offset, str) => {
        for (let i = 0; i < str.length; i += 1) view.setUint8(offset + i, str.charCodeAt(i));
      };
      writeStr(0, "RIFF");
      view.setUint32(4, 36 + samples.length * 2, true);
      writeStr(8, "WAVE");
      writeStr(12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeStr(36, "data");
      view.setUint32(40, samples.length * 2, true);
      let offset = 44;
      for (let i = 0; i < samples.length; i += 1) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
        offset += 2;
      }
      return new Blob([buffer], { type: "audio/wav" });
    },

    _downsample(buffer, fromRate, toRate) {
      if (fromRate === toRate) return buffer;
      const ratio = fromRate / toRate;
      const newLen = Math.round(buffer.length / ratio);
      const result = new Float32Array(newLen);
      for (let i = 0; i < newLen; i += 1) {
        const idx = Math.floor(i * ratio);
        result[i] = buffer[idx] || 0;
      }
      return result;
    },

    /**
     * 开始录音（优先 AudioContext 采集 PCM → 最终转 WAV 16kHz）
     */
    async startRecording() {
      if (this._recording) return;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("当前浏览器不支持麦克风录音");
      }

      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
      } catch (err) {
        const name = err && err.name;
        if (name === "NotAllowedError" || name === "PermissionDeniedError") {
          throw new Error("未获得麦克风权限，请在浏览器设置中允许使用麦克风后重试");
        }
        if (name === "NotFoundError") {
          throw new Error("未检测到麦克风设备");
        }
        throw new Error("无法打开麦克风：" + (err.message || "未知错误"));
      }

      this._mediaStream = stream;
      this._pcmChunks = [];
      this._chunks = [];
      this._recording = true;

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this._audioCtx = new AudioCtx();
      this._source = this._audioCtx.createMediaStreamSource(stream);
      // ScriptProcessor 兼容性较好（移动端也可用）
      const bufferSize = 4096;
      this._processor = this._audioCtx.createScriptProcessor(bufferSize, 1, 1);
      this._processor.onaudioprocess = (event) => {
        if (!this._recording) return;
        const input = event.inputBuffer.getChannelData(0);
        this._pcmChunks.push(new Float32Array(input));
      };
      this._source.connect(this._processor);
      this._processor.connect(this._audioCtx.destination);

      // 同步用 MediaRecorder 作兜底（部分环境 ScriptProcessor 受限）
      try {
        const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        this._mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
        this._mediaRecorder.ondataavailable = (e) => {
          if (e.data && e.data.size) this._chunks.push(e.data);
        };
        this._mediaRecorder.start(200);
      } catch (_err) {
        this._mediaRecorder = null;
      }
    },

    /** 停止录音并返回 WAV Blob（16kHz mono） */
    async stopRecording() {
      if (!this._recording) throw new Error("当前没有在录音");
      this._recording = false;

      if (this._mediaRecorder && this._mediaRecorder.state !== "inactive") {
        await new Promise((resolve) => {
          this._mediaRecorder.onstop = resolve;
          try {
            this._mediaRecorder.stop();
          } catch (_err) {
            resolve();
          }
        });
      }

      if (this._processor) {
        try {
          this._processor.disconnect();
        } catch (_err) {
          /* ignore */
        }
      }
      if (this._source) {
        try {
          this._source.disconnect();
        } catch (_err) {
          /* ignore */
        }
      }
      if (this._mediaStream) {
        this._mediaStream.getTracks().forEach((t) => t.stop());
      }

      const sampleRate = (this._audioCtx && this._audioCtx.sampleRate) || 44100;
      if (this._audioCtx) {
        try {
          await this._audioCtx.close();
        } catch (_err) {
          /* ignore */
        }
      }
      this._audioCtx = null;
      this._processor = null;
      this._source = null;
      this._mediaStream = null;
      this._mediaRecorder = null;

      let total = 0;
      this._pcmChunks.forEach((c) => {
        total += c.length;
      });
      if (total < 1600) {
        throw new Error("录音太短，请再说长一点");
      }
      const merged = new Float32Array(total);
      let offset = 0;
      this._pcmChunks.forEach((c) => {
        merged.set(c, offset);
        offset += c.length;
      });
      this._pcmChunks = [];
      const down = this._downsample(merged, sampleRate, 16000);
      return this._encodeWav(down, 16000);
    },

    /**
     * 上传音频识别为文字
     * @param {Blob} audioBlob
     */
    async recognizeSpeech(audioBlob) {
      if (!audioBlob || !audioBlob.size) throw new Error("没有可识别的音频");
      let lastError = null;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const form = new FormData();
          form.append("audio", audioBlob, "answer.wav");
          form.append("format", "wav");
          form.append("rate", "16000");
          const resp = await fetch("/api/speech/recognize", {
            method: "POST",
            body: form,
          });
          const data = await resp.json();
          if (!resp.ok || !data.ok) {
            throw new Error(data.error || "语音识别失败");
          }
          return String(data.text || "").trim();
        } catch (err) {
          lastError = err;
          await new Promise((r) => setTimeout(r, 400));
        }
      }
      throw lastError || new Error("语音识别失败");
    },

    /** 柔和评判答案 */
    async evaluateAnswer(text, question) {
      const resp = await fetch("/api/speech/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, question }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "评判失败");
      return data;
    },
  };

  window.SpeechService = SpeechService;
})();
