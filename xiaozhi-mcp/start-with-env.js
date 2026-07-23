/**
 * 从 .env 读取接入点并启动 mcp_exe（Windows 友好）
 */
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const envPath = path.join(__dirname, ".env");
if (!fs.existsSync(envPath)) {
  console.error("缺少 .env，请填写 XIAOZHI_MCP_ENDPOINT");
  process.exit(1);
}

const endpoint = fs
  .readFileSync(envPath, "utf8")
  .split(/\r?\n/)
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith("#"))
  .map((l) => {
    const i = l.indexOf("=");
    return i > 0 ? [l.slice(0, i), l.slice(i + 1)] : null;
  })
  .filter(Boolean)
  .find(([k]) => k === "XIAOZHI_MCP_ENDPOINT");

if (!endpoint || !endpoint[1]) {
  console.error(".env 中未找到 XIAOZHI_MCP_ENDPOINT");
  process.exit(1);
}

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const child = spawn(
  npx,
  [
    "--yes",
    "mcp_exe",
    "--ws",
    endpoint[1],
    "--mcp-config",
    "./mcp-config.json",
    "--mcp-js",
    "./custom-mcp.js",
    "--server-name",
    "memory-harbor-xiaozhi",
    "--log-level",
    "INFO",
  ],
  { cwd: __dirname, stdio: "inherit", shell: true, env: process.env }
);

child.on("exit", (code) => process.exit(code || 0));
