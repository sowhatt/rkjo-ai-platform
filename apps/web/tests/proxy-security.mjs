/** Real Next HTTP routes; synthetic upstream only tests the web trust boundary. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';

const calls = [];
const upstream = createServer(async (req, res) => {
  let body = ''; for await (const part of req) body += part;
  calls.push({ url: req.url, headers: req.headers, body });
  if (req.headers.authorization === 'Bearer redirect') {
    res.writeHead(302, { Location: '/credential-trap' }); res.end(); return;
  }
  if (req.headers.authorization === 'Bearer html') {
    res.writeHead(500, { 'Content-Type': 'text/html' }); res.end('private upstream diagnostic'); return;
  }
  res.writeHead(200, { 'Content-Type': 'application/json', 'Set-Cookie': 'unsafe=1' });
  res.end(JSON.stringify({ ok: true }));
});
upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
const reserved = createServer(); reserved.listen(0, '127.0.0.1'); await once(reserved, 'listening');
const port = reserved.address().port; await new Promise(r => reserved.close(r));
const next = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], {
  env: { ...process.env, RKJO_API_URL: `http://127.0.0.1:${upstream.address().port}`,
    RKJO_OPERATOR_API_KEY: 'synthetic-shared-operator', RKJO_VIEWER_API_KEY: 'synthetic-shared-viewer' },
  stdio: ['ignore', 'pipe', 'pipe'],
});
try {
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Next startup timeout')), 20000);
    next.stdout.on('data', data => { if (data.toString().includes('Ready')) { clearTimeout(timer); resolve(); } });
    next.on('exit', code => { clearTimeout(timer); reject(Error(`Next exited: ${code}`)); });
  });
  const cases = [
    ['GET', '/education/courses'], ['POST', '/education/courses'],
    ['GET', '/education/courses/course-a'], ['POST', '/education/courses/course-a/documents'],
    ['POST', '/rag/answer'], ['POST', '/rag/documents'],
  ];
  for (const [method, path] of cases) {
    const url = `http://127.0.0.1:${port}/api${path}`;
    for (const headers of [{}, { 'X-API-Key': 'synthetic-shared-operator' }, { Authorization: 'Bearer' }]) {
      const response = await fetch(url, { method, headers });
      assert.equal(response.status, 401, `${method} ${path} must reject anonymous/malformed credentials`);
    }
  }
  assert.equal(calls.length, 0, 'Rejected requests must not reach upstream');
  for (const [method, path] of cases) {
    const response = await fetch(`http://127.0.0.1:${port}/api${path}`, {
      method, headers: { Authorization: 'Bearer caller-a', 'X-Tenant-ID': 'forged', Cookie: 'private=1', 'Content-Type': 'application/json' },
      body: method === 'POST' ? '{"test":"payload"}' : undefined,
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.equal(response.headers.get('set-cookie'), null);
    const call = calls.at(-1);
    assert.equal(call.url, path);
    assert.equal(call.headers.authorization, 'Bearer caller-a');
    for (const header of ['x-api-key', 'x-tenant-id', 'cookie']) assert.equal(call.headers[header], undefined);
    if (method === 'POST') assert.equal(call.body, '{"test":"payload"}');
  }
  for (const token of ['redirect', 'html']) {
    const before = calls.length;
    const r = await fetch(`http://127.0.0.1:${port}/api/education/courses`, { headers: { Authorization: `Bearer ${token}` } });
    assert.equal(r.status, 502); assert.equal(calls.length, before + 1);
    assert.ok(!(await r.text()).includes('private upstream'));
  }
  console.log('PASS: 6 real Next routes; anonymous rejection, caller identity, header isolation, redirects, safe errors. Synthetic upstream.');
} finally {
  next.kill(); if (next.exitCode === null) await once(next, 'exit');
  await new Promise(r => upstream.close(r));
}
