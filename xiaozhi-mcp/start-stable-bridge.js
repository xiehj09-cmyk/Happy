/**
 * 稳定小智 MCP 桥接（绕过 mcp_exe 的已知问题）：
 * 1. 禁用 mcp-config / custom-mcp 的 fs.watchFile（Docker overlay 会误触发重启 → 双连接）
 * 2. 每次 WebSocket 连接使用全新 McpRouterServer，避免
 *    "Already connected to a transport"
 * 3. 单实例进程内重连，不拉起第二套 MCP
 */
"use strict";

const fs = require("fs");
const path = require("path");
const WebSocket = require("ws");

// 必须在加载 mcp_exe 之前禁用热重载监听
const _watchFile = fs.watchFile.bind(fs);
fs.watchFile = function watchFileDisabled(filename, ...rest) {
  const name = String(filename);
  if (
    name.includes("mcp-config") ||
    name.includes("custom-mcp") ||
    name.endsWith(".json") ||
    name.endsWith(".js")
  ) {
    console.log(
      `${new Date().toISOString()} - INFO - 已跳过文件监听: ${path.basename(name)}`
    );
    return;
  }
  return _watchFile(filename, ...rest);
};

const {
  McpRouterServer,
} = require("mcp_exe/dist/mcpRouterServer.js");
const {
  WebSocketServerTransport,
} = require("mcp_exe/dist/webSocketTransport.js");

const INITIAL_BACKOFF = 1000;
const MAX_BACKOFF = 120000;

function loadDotEnvFile() {
  const envPath = path.join(__dirname, ".env");
  const map = {};
  if (!fs.existsSync(envPath)) return map;
  fs.readFileSync(envPath, "utf8")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#") && l.includes("="))
    .forEach((l) => {
      const i = l.indexOf("=");
      map[l.slice(0, i).trim()] = l.slice(i + 1).trim();
    });
  return map;
}

function syncEnvFromFile() {
  const fileEnv = loadDotEnvFile();
  if (!process.env.WEBSITE_BASE && fileEnv.WEBSITE_BASE) {
    process.env.WEBSITE_BASE = fileEnv.WEBSITE_BASE;
  }
  if (!process.env.WEBSITE_MCP_TOKEN) {
    process.env.WEBSITE_MCP_TOKEN =
      fileEnv.WEBSITE_MCP_TOKEN || fileEnv.MCP_API_TOKEN || "";
  }
  if (!process.env.MCP_API_TOKEN && process.env.WEBSITE_MCP_TOKEN) {
    process.env.MCP_API_TOKEN = process.env.WEBSITE_MCP_TOKEN;
  }
  return fileEnv;
}

function log(level, msg) {
  const line = `${new Date().toISOString()} - ${level} - ${msg}`;
  if (level === "ERROR" || level === "WARN") {
    console.error(line);
  } else {
    console.log(line);
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function createFreshRouter(serverInfo, mcpConfig, configureMcp) {
  const router = new McpRouterServer(serverInfo, { transportType: "stdio" });
  await router.importMcpConfig(mcpConfig, configureMcp);
  return router;
}

async function safeCloseRouter(router) {
  if (!router) return;
  try {
    await router.close();
  } catch (e) {
    log("WARN", `关闭旧 MCP 路由时忽略: ${e && e.message ? e.message : e}`);
  }
}

async function runBridge(endpoint) {
  const mcpConfig = JSON.parse(
    fs.readFileSync(path.join(__dirname, "mcp-config.json"), "utf8")
  );
  const custom = require(path.join(__dirname, "custom-mcp.js"));
  const configureMcp = custom.configureMcp;
  const serverInfo = {
    name:
      (mcpConfig.serverInfo && mcpConfig.serverInfo.serverName) ||
      "memory-harbor-xiaozhi",
    version: "1.0.0",
  };

  let isRunning = true;
  let reconnectAttempt = 0;
  let backoff = INITIAL_BACKOFF;
  let currentWs = null;
  let routerServer = null;

  const shutdown = async () => {
    if (!isRunning) return;
    isRunning = false;
    log("INFO", "正在关闭稳定桥接...");
    if (currentWs) {
      try {
        currentWs.removeAllListeners();
        if (currentWs.readyState === WebSocket.OPEN) currentWs.close();
      } catch (_) {}
      currentWs = null;
    }
    await safeCloseRouter(routerServer);
    routerServer = null;
  };

  process.on("SIGINT", () => {
    shutdown().finally(() => process.exit(0));
  });
  process.on("SIGTERM", () => {
    shutdown().finally(() => process.exit(0));
  });

  log(
    "INFO",
    `稳定桥接启动 · 网站=${process.env.WEBSITE_BASE || "http://127.0.0.1:5000"} · endpoint=${endpoint.slice(0, 48)}...`
  );

  while (isRunning) {
    try {
      if (reconnectAttempt > 0) {
        const waitTime = backoff * (1 + Math.random() * 0.1);
        log(
          "INFO",
          `等待 ${(waitTime / 1000).toFixed(2)} 秒后进行第 ${reconnectAttempt} 次重连...`
        );
        await sleep(waitTime);
        if (!isRunning) break;
      }

      await new Promise((resolve, reject) => {
        log("INFO", "正在连接到WebSocket服务器...");
        const ws = new WebSocket(endpoint);
        currentWs = ws;
        let settled = false;

        const fail = async (err) => {
          if (settled) return;
          settled = true;
          ws.removeAllListeners();
          try {
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
              ws.close();
            }
          } catch (_) {}
          await safeCloseRouter(routerServer);
          routerServer = null;
          currentWs = null;
          reject(err instanceof Error ? err : new Error(String(err)));
        };

        ws.on("open", async () => {
          log("INFO", "成功连接到WebSocket服务器");
          reconnectAttempt = 0;
          backoff = INITIAL_BACKOFF;

          try {
            // 关键：每次连接都新建 Protocol，绝不复用已 connect 的实例
            await safeCloseRouter(routerServer);
            routerServer = null;

            log("INFO", "正在启动MCP服务器...");
            const transport = new WebSocketServerTransport(ws);

            ws.on("message", (data) => {
              try {
                const raw = data.toString("utf-8");
                log("DEBUG", `<< ${raw.slice(0, 320)}...`);
                const jsonMessage = JSON.parse(raw);
                const tryProcess = (message, attempt = 0) => {
                  if (transport.onmessage) {
                    transport.onmessage(message);
                  } else if (attempt < 100) {
                    if (attempt === 0 || attempt % 20 === 19) {
                      log("DEBUG", `等待onmessage可用，尝试次数: ${attempt + 1}`);
                    }
                    setTimeout(() => tryProcess(message, attempt + 1), 50);
                  } else {
                    log("ERROR", "达到最大重试次数，消息处理失败");
                  }
                };
                tryProcess(jsonMessage);
              } catch (error) {
                log("ERROR", `处理消息时出错: ${error}`);
              }
            });

            routerServer = await createFreshRouter(
              serverInfo,
              mcpConfig,
              configureMcp
            );
            await routerServer.getActiveServer().connect(transport);
            log("INFO", "MCP服务器启动成功");
          } catch (error) {
            log("ERROR", `启动MCP服务器失败: ${error}`);
            await fail(error);
          }
        });

        ws.on("close", () => {
          log("ERROR", "WebSocket连接已关闭");
          fail(new Error("WebSocket连接已关闭"));
        });

        ws.on("error", (error) => {
          log("ERROR", `WebSocket错误: ${error}`);
          fail(error);
        });
      });
    } catch (e) {
      if (!isRunning) break;
      reconnectAttempt += 1;
      log("WARN", `连接关闭 (尝试次数: ${reconnectAttempt}): ${e}`);
      backoff = Math.min(backoff * 2, MAX_BACKOFF);
    }
  }
}

async function main() {
  const fileEnv = syncEnvFromFile();
  const endpoint =
    process.env.XIAOZHI_MCP_ENDPOINT || fileEnv.XIAOZHI_MCP_ENDPOINT || "";
  if (!endpoint) {
    console.error("缺少 XIAOZHI_MCP_ENDPOINT（环境变量或 .env）");
    process.exit(1);
  }
  await runBridge(endpoint);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
