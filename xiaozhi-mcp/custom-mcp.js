/**
 * 挂到小智 AI 的自定义工具（记忆港湾）
 * 1) 语音事项写入 txt，并同步到网站
 * 2) 询问今日用药 → 读取网站用药计划
 * 3) 老人完成事项/服药 → 回写网站状态
 */
const fs = require("fs");
const path = require("path");
const http = require("http");
const https = require("https");
const { URL } = require("url");

const NOTES_FILE = path.join(__dirname, "data", "voice_notes.txt");
const ENV_FILE = path.join(__dirname, ".env");

function parseXiaozhiIds(endpoint) {
  const out = { userId: "", agentId: "" };
  if (!endpoint) return out;
  try {
    const u = new URL(endpoint);
    const jwt = u.searchParams.get("token") || "";
    const part = jwt.split(".")[1];
    if (!part) return out;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const payload = JSON.parse(Buffer.from(pad, "base64").toString("utf8"));
    if (payload.userId != null) out.userId = String(payload.userId);
    if (payload.agentId != null) out.agentId = String(payload.agentId);
  } catch (_e) {
    /* ignore */
  }
  return out;
}

function loadEnv() {
  const out = {
    WEBSITE_BASE: "http://127.0.0.1:5000",
    WEBSITE_MCP_TOKEN: "",
    XIAOZHI_MCP_ENDPOINT: "",
  };
  // 1) 本目录 .env（本机开发）
  if (fs.existsSync(ENV_FILE)) {
    fs.readFileSync(ENV_FILE, "utf8")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && l.includes("="))
      .forEach((l) => {
        const i = l.indexOf("=");
        const k = l.slice(0, i).trim();
        const v = l.slice(i + 1).trim();
        if (k === "WEBSITE_BASE" || k === "MCP_API_BASE") out.WEBSITE_BASE = v.replace(/\/$/, "");
        if (k === "WEBSITE_MCP_TOKEN" || k === "MCP_API_TOKEN") out.WEBSITE_MCP_TOKEN = v;
        if (k === "XIAOZHI_MCP_ENDPOINT") out.XIAOZHI_MCP_ENDPOINT = v;
      });
  }
  // 2) 进程环境变量优先（Docker Compose）
  if (process.env.WEBSITE_BASE || process.env.MCP_API_BASE) {
    out.WEBSITE_BASE = (process.env.WEBSITE_BASE || process.env.MCP_API_BASE).replace(/\/$/, "");
  }
  if (process.env.WEBSITE_MCP_TOKEN || process.env.MCP_API_TOKEN) {
    out.WEBSITE_MCP_TOKEN = process.env.WEBSITE_MCP_TOKEN || process.env.MCP_API_TOKEN;
  }
  if (process.env.XIAOZHI_MCP_ENDPOINT) {
    out.XIAOZHI_MCP_ENDPOINT = process.env.XIAOZHI_MCP_ENDPOINT;
  }
  const ids = parseXiaozhiIds(out.XIAOZHI_MCP_ENDPOINT);
  out.XIAOZHI_USER_ID = process.env.XIAOZHI_USER_ID || ids.userId || "";
  out.XIAOZHI_AGENT_ID = process.env.XIAOZHI_AGENT_ID || ids.agentId || "";
  return out;
}

const ENV = loadEnv();

function ensureNotesFile() {
  const dir = path.dirname(NOTES_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(NOTES_FILE)) {
    fs.writeFileSync(
      NOTES_FILE,
      "# 语音事项记录本\n# 由小智 MCP 工具自动写入，并同步到记忆港湾网站\n",
      "utf8"
    );
  }
}

function nowStamp() {
  return new Date().toLocaleString("zh-CN", { hour12: false });
}

function readNoteLines() {
  ensureNotesFile();
  return fs
    .readFileSync(NOTES_FILE, "utf8")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"));
}

function softMatch(line, key) {
  if (!key) return true;
  if (line.includes(key)) return true;
  let i = 0;
  for (const ch of line) {
    if (ch === key[i]) i += 1;
    if (i >= key.length) return true;
  }
  return false;
}

function apiRequest(method, apiPath, body) {
  return new Promise((resolve, reject) => {
    if (!ENV.WEBSITE_MCP_TOKEN) {
      reject(new Error("未配置 WEBSITE_MCP_TOKEN，无法同步到网站"));
      return;
    }
    const url = new URL(apiPath, ENV.WEBSITE_BASE);
    const payload = body ? JSON.stringify(body) : null;
    const lib = url.protocol === "https:" ? https : http;
    const req = lib.request(
      {
        hostname: url.hostname,
        port: url.port || (url.protocol === "https:" ? 443 : 80),
        path: url.pathname + url.search,
        method,
        headers: {
          Authorization: "Bearer " + ENV.WEBSITE_MCP_TOKEN,
          "Content-Type": "application/json",
          ...(ENV.XIAOZHI_USER_ID ? { "X-Xiaozhi-User-Id": ENV.XIAOZHI_USER_ID } : {}),
          ...(ENV.XIAOZHI_AGENT_ID ? { "X-Xiaozhi-Agent-Id": ENV.XIAOZHI_AGENT_ID } : {}),
          ...(payload ? { "Content-Length": Buffer.byteLength(payload) } : {}),
        },
        timeout: 12000,
      },
      (res) => {
        let raw = "";
        res.on("data", (c) => (raw += c));
        res.on("end", () => {
          let data = {};
          try {
            data = raw ? JSON.parse(raw) : {};
          } catch (_e) {
            data = { ok: false, error: raw.slice(0, 200) };
          }
          if (res.statusCode >= 400 || data.ok === false) {
            reject(new Error(data.error || "网站接口错误 " + res.statusCode));
            return;
          }
          resolve(data);
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("连接网站超时，请确认记忆港湾已在本机运行"));
    });
    if (payload) req.write(payload);
    req.end();
  });
}

function okText(text) {
  return { content: [{ type: "text", text }] };
}

function errText(err) {
  return {
    content: [{ type: "text", text: (err && err.message) || String(err) }],
    isError: true,
  };
}

module.exports = {
  configureMcp: function (server, ResourceTemplate, z) {
    ensureNotesFile();

    server.tool(
      "memory_harbor_ping",
      "记忆港湾 MCP 连通性检查。",
      {},
      async () =>
        okText(
          "记忆港湾 MCP 已连接。" +
            nowStamp() +
            "。网站：" +
            ENV.WEBSITE_BASE +
            "。Token：" +
            (ENV.WEBSITE_MCP_TOKEN ? "已配置" : "未配置") +
            "。小智用户：" +
            (ENV.XIAOZHI_USER_ID || "未解析")
        )
    );

    server.tool(
      "care_tip",
      "给家属或长者一句温暖、简短的照护提醒。参数 topic 可选：用药 / 陪伴 / 安全 / 训练。",
      {
        topic: z.enum(["用药", "陪伴", "安全", "训练"]).optional().describe("提醒主题"),
      },
      async ({ topic }) => {
        const tips = {
          用药: "服药尽量固定时间，吃完在清单里点一下，方便家人核对。",
          陪伴: "一次只问一件事，慢慢等回答，少纠正细节，多说您说得很好。",
          安全: "出门前确认门锁与钥匙；有异常告警时先处理安全，再处理其他事。",
          训练: "记忆小练习没有对错，说出来就很好；累了可以先休息。",
        };
        return okText(tips[topic || "陪伴"] || tips["陪伴"]);
      }
    );

    /** 1. 语音录入事项 → txt + 同步网站 */
    server.tool(
      "voice_note_write",
      "把语音转写后的事项写入本地 txt，并同步到记忆港湾网站「语音事项」。用于「帮我记一下…」。",
      {
        text: z.string().min(1).describe("要记录的事项内容"),
      },
      async ({ text }) => {
        const body = String(text || "").trim();
        if (!body) return errText(new Error("没有听到可记录的内容"));
        ensureNotesFile();
        const line = `${nowStamp()} | ${body.replace(/\s+/g, " ")}\n`;
        fs.appendFileSync(NOTES_FILE, line, "utf8");
        let syncMsg = "";
        try {
          const data = await apiRequest("POST", "/api/mcp/matters", { text: body });
          const id = data.matter && data.matter.id;
          syncMsg = id ? `已同步到网站（事项 #${id}）。` : "已同步到网站。";
        } catch (e) {
          syncMsg = "本地已保存，但同步网站失败：" + (e.message || e) + "。";
        }
        const total = readNoteLines().length;
        return okText(`已记下：${body}\n${syncMsg}本地共 ${total} 条。`);
      }
    );

    server.tool(
      "voice_note_query",
      "查询语音事项：优先查网站，失败则查本地 txt。可按关键词搜索。",
      {
        keyword: z.string().optional().describe("可选关键词"),
        limit: z.number().int().min(1).max(50).optional().describe("最多条数，默认 10"),
      },
      async ({ keyword, limit }) => {
        const max = limit || 10;
        const key = (keyword || "").trim();
        try {
          const q =
            "/api/mcp/matters?status=all&limit=" +
            max +
            (key ? "&keyword=" + encodeURIComponent(key) : "");
          const data = await apiRequest("GET", q);
          const items = data.matters || [];
          if (!items.length) {
            return okText(
              key
                ? `网站上没有找到包含「${key}」的事项。`
                : "网站事项还是空的。可以说「帮我记一下……」。"
            );
          }
          const lines = items.map(
            (m, i) =>
              `${i + 1}. [#${m.id}] ${m.body}（${m.status_label || m.status}）· ${m.created_at || ""}`
          );
          return okText(
            (key ? `网站找到 ${items.length} 条与「${key}」相关：` : `网站最近 ${items.length} 条事项：`) +
              "\n\n" +
              lines.join("\n")
          );
        } catch (_e) {
          const lines = readNoteLines();
          let matched = lines;
          if (key) matched = lines.filter((l) => softMatch(l, key));
          if (!matched.length) {
            return okText("暂时连不上网站，本地也没有匹配事项。");
          }
          const slice = matched.slice(-max);
          return okText(
            "（网站暂不可用，以下为本地备份）\n" +
              slice.map((l, i) => `${i + 1}. ${l}`).join("\n")
          );
        }
      }
    );

    /** 2. 今日要吃什么药 → 网站用药 */
    server.tool(
      "today_medication_query",
      "查询记忆港湾网站中「今天要吃什么药」。当用户问今日用药、还有哪些药没吃时调用。",
      {},
      async () => {
        try {
          const data = await apiRequest("GET", "/api/mcp/medication/today");
          return okText(data.speak || "今天没有用药安排。");
        } catch (e) {
          return errText(e);
        }
      }
    );

    /** 3. 完成事项 → 网站状态 */
    server.tool(
      "voice_note_complete",
      "把语音事项标记为已完成，并同步修改网站状态。用于「这件事做完了」「勾掉买药那条」。",
      {
        keyword: z.string().optional().describe("事项关键词或原文片段"),
        matter_id: z.number().int().optional().describe("网站事项 id"),
      },
      async ({ keyword, matter_id }) => {
        try {
          const data = await apiRequest("POST", "/api/mcp/matters/complete", {
            keyword: keyword || "",
            matter_id: matter_id || null,
          });
          const m = data.matter || {};
          return okText(
            `好的，已在网站把事项标为完成：${m.body || keyword || "#" + m.id}`
          );
        } catch (e) {
          return errText(e);
        }
      }
    );

    /** 3b. 吃药完成 → 网站服药状态 */
    server.tool(
      "medication_mark_taken",
      "老人说某药已吃完时，在网站标记该药今日已服用。用于「降压药我吃过了」。",
      {
        name: z.string().min(1).describe("药名或别名，如：降压药、阿司匹林"),
      },
      async ({ name }) => {
        try {
          const data = await apiRequest("POST", "/api/mcp/medication/taken", {
            name,
          });
          return okText(data.speak || "已记录服药。");
        } catch (e) {
          return errText(e);
        }
      }
    );
  },
};
