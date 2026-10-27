import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..');
const types = {'.html':'text/html', '.css':'text/css', '.mjs':'text/javascript', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png', '.webp':'image/webp'};
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    const name = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
    const target = path.resolve(root, '.' + name);
    if (!target.startsWith(root + path.sep)) { response.writeHead(403).end(); return; }
    const data = await fs.readFile(target);
    response.writeHead(200, {'Content-Type': types[path.extname(target)] || 'application/octet-stream', 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'}).end(data);
  } catch { response.writeHead(404).end('Not found'); }
});
server.listen(4173, '127.0.0.1', () => console.log('Local: http://127.0.0.1:4173'));
