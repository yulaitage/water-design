import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';
import http from 'http';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API_HOST = '127.0.0.1';
const API_PORT = 8000;
const API_BASE = '/api/v1';

async function startServer() {
  const app = express();
  const PORT = 3000;

  // Buffered API proxy — collect full body, forward to backend
  app.use('/api', (req, res) => {
    const proxyPath = API_BASE + req.url;
    const chunks: Buffer[] = [];
    let settled = false;
    const once = (fn: () => void) => { if (!settled) { settled = true; fn(); } };

    req.on('data', (chunk: Buffer) => chunks.push(chunk));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      const start = Date.now();

      // Strip Expect: 100-continue to prevent browser hang
      const headers = { ...req.headers, host: `${API_HOST}:${API_PORT}` };
      delete headers['expect'];

      const proxyReq = http.request(
        { hostname: API_HOST, port: API_PORT, path: proxyPath, method: req.method, headers },
        (proxyRes) => {
          const elapsed = ((Date.now() - start) / 1000).toFixed(1);
          console.log(`[proxy] ${req.method} ${req.url} <- ${proxyRes.statusCode} (${elapsed}s)`);
          once(() => { res.writeHead(proxyRes.statusCode || 500, proxyRes.headers); proxyRes.pipe(res); });
        },
      );

      proxyReq.setTimeout(300_000, () => {
        console.error(`[proxy timeout] ${req.url} after 300s`);
        proxyReq.destroy();
        once(() => { res.writeHead(504, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ detail: 'Backend timeout' })); });
      });

      proxyReq.on('error', (err) => {
        console.error(`[proxy error] ${req.url}: ${err.message}`);
        once(() => { res.writeHead(502, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ detail: `Backend error: ${err.message}` })); });
      });

      proxyReq.end(body);
    });

    req.on('error', (err) => {
      console.error(`[req error] ${req.url}: ${err.message}`);
      once(() => { res.writeHead(400, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ detail: 'Request error' })); });
    });
  });

  app.use(express.json());

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: 'spa' });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => res.sendFile(path.join(distPath, 'index.html')));
  }

  const server = app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log(`API proxy: /api/* -> http://${API_HOST}:${API_PORT}${API_BASE}/*`);
  });

  server.timeout = 600_000;
  server.keepAliveTimeout = 120_000;
  server.headersTimeout = 120_000;
}

startServer().catch((err) => { console.error('Failed to start server:', err); process.exit(1); });
