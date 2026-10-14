import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handle } from './worker.mjs';
const page = () => new Request('https://aedrova.com/', { headers: { accept: 'text/html' } });
for (const status of [500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526]) {
  test(`origin ${status} is branded and status preserved`, async () => {
    const response = await handle(page(), async () => new Response('host internals', { status }));
    assert.equal(response.status, status);
    assert.match(await response.text(), /We’ll be right back/);
    assert.equal(response.headers.get('cache-control'), 'no-store');
  });
}
test('unreachable origin gets standalone fallback', async () => {
  const response = await handle(page(), async () => { throw new Error('host secret'); });
  assert.equal(response.status, 503);
  const html = await response.text();
  assert.ok(!html.includes('host secret') && html.includes('data:image/png;base64,'));
});
test('API, static, POST, redirects and successful pages remain unchanged', async () => {
  for (const request of [new Request('https://aedrova.com/api/check', {headers:{accept:'text/html'}}), new Request('https://aedrova.com/static/test', {headers:{accept:'text/html'}}), new Request('https://aedrova.com/', {method:'POST',headers:{accept:'text/html'}})]) {
    const upstream = new Response('original', {status:503});
    assert.equal(await handle(request, async()=>upstream),upstream);
  }
  for (const status of [200, 302, 404]) {
    const upstream = new Response('original', {status});
    assert.equal(await handle(page(), async()=>upstream),upstream);
  }
});
