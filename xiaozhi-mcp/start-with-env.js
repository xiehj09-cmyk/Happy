/**
 * 启动小智 MCP：优先读环境变量（Docker），其次读本目录 .env
 */
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const envPath = path.join(__dirname, ".env");

function loadDotEnvFile() {
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

const fileEnv = loadDotEnvFile();
const endpoint =
  process.env.XIAOZHI_MCP_ENDPOINT || fileEnv.XIAOZHI_MCP_ENDPOINT || "";

if (!endpoint) {
  console.error("缺少 XIAOZHI_MCP_ENDPOINT（环境变量或 .env）");
  process.exit(1);
}

// 同步关键环境变量，供 custom-mcp.js 使用
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

const localBin = path.join(
  __dirname,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "mcp_exe.cmd" : "mcp_exe"
);
const useLocal = fs.existsSync(localBin);
const cmd = useLocal ? localBin : process.platform === "win32" ? "npx.cmd" : "npx";
const args = useLocal
  ? [
      "--ws",
      endpoint,
      "--mcp-config",
      "./mcp-config.json",
      "--mcp-js",
      "./custom-mcp.js",
      "--server-name",
      "memory-harbor-xiaozhi",
      "--log-level",
      "INFO",
    ]
  : [
      "--yes",
      "mcp_exe",
      "--ws",
      endpoint,
      "--mcp-config",
      "./mcp-config.json",
      "--mcp-js",
      "./custom-mcp.js",
      "--server-name",
      "memory-harbor-xiaozhi",
      "--log-level",
      "INFO",
    ];

console.log(
  "启动小智 MCP · 网站=" +
    (process.env.WEBSITE_BASE || "http://127.0.0.1:5000") +
    " · " +
    (useLocal ? "本地 mcp_exe" : "npx mcp_exe")
);

const child = spawn(cmd, args, {
  cwd: __dirname,
  stdio: "inherit",
  shell: process.platform === "win32",
  env: process.env,
});

child.on("exit", (code) => process.exit(code || 0));
