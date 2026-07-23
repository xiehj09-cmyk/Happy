# 小智 MCP 桥接（Node + mcp_exe）
FROM node:20-bookworm-slim

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY custom-mcp.js mcp-config.json start-with-env.js ./
RUN mkdir -p /app/data

ENV WEBSITE_BASE=http://web:5000 \
    NODE_ENV=production

CMD ["node", "start-with-env.js"]
