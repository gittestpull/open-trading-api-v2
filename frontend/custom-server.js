// Wrapper around Next.js standalone server.js that adds WS proxy
import { createServer } from "http";
import httpProxy from "http-proxy";

const port = parseInt(process.env.PORT || "3000", 10);
const BACKEND = process.env.API_URL || "http://trading-web:8080";

// Create proxy for API and WS
const proxy = httpProxy.createProxyServer({
  target: BACKEND,
  ws: true,
  changeOrigin: true,
});

proxy.on("error", (err, _req, res) => {
  console.error(`Failed to proxy ${_req?.url}`, err.message);
  if (res && typeof res.writeHead === "function") {
    res.writeHead(502, { "Content-Type": "text/plain" });
    res.end("Bad Gateway");
  }
});

// Import the Next.js standalone handler
const nextHandler = (await import("./server.js")).default;

// Patch: intercept the existing server's listen to capture it
const origListen = createServer.prototype?.listen;

// Actually, Next.js standalone server.js calls process.env.PORT and creates
// its own http server. We need a different approach.
// 
// Strategy: Start a thin proxy server that handles /ws/* upgrades,
// and forwards everything else to the Next.js standalone (which already 
// proxies /api/* via rewrites).

// We'll run Next.js standalone on a different internal port
const NEXT_INTERNAL_PORT = 3001;
process.env.PORT = String(NEXT_INTERNAL_PORT);
process.env.HOSTNAME = "0.0.0.0";

// Import server.js which will start Next.js on port 3001
await import("./server.js");

// Now create our wrapper server on the real port
const nextProxy = httpProxy.createProxyServer({
  target: `http://127.0.0.1:${NEXT_INTERNAL_PORT}`,
  ws: true,
});

nextProxy.on("error", (err, _req, res) => {
  console.error(`Next proxy error:`, err.message);
  if (res && typeof res.writeHead === "function") {
    res.writeHead(502);
    res.end("Next.js unavailable");
  }
});

const wrapperServer = createServer((req, res) => {
  // Proxy /api/* directly to backend (bypass Next.js rewrites for reliability)
  if (req.url?.startsWith("/api/")) {
    proxy.web(req, res);
  } else {
    // Everything else goes to Next.js
    nextProxy.web(req, res);
  }
});

// WebSocket upgrade
wrapperServer.on("upgrade", (req, socket, head) => {
  if (req.url?.startsWith("/ws/")) {
    // WebSocket to backend
    proxy.ws(req, socket, head);
  } else {
    // Next.js HMR etc (shouldn't happen in prod)
    nextProxy.ws(req, socket, head);
  }
});

wrapperServer.listen(port, "0.0.0.0", () => {
  console.log(`> Ready on http://0.0.0.0:${port}`);
  console.log(`> Proxying /api/* and /ws/* to ${BACKEND}`);
  console.log(`> Next.js on internal port ${NEXT_INTERNAL_PORT}`);
});
