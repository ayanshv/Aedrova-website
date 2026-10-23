import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handle } from './worker.mjs';
import { ROBOTS, SITEMAP } from './robots.mjs';
for (const host of ['aedrova.com', 'www.aedrova.com']) {
  for (const method of ['GET', 'HEAD']) {
    test(`${host} ${method} robots survives origin outage`, async () => {
      const response = await handle(new Request(`https://${host}/robots.txt`, {method}), () => {throw Error('origin down');});
      assert.equal(response.status, 200);
      const text = await response.text();
      if (method === 'HEAD') assert.equal(text, '');
      else {
        assert.match(text, /Sitemap: https:\/\/aedrova.com\/sitemap.xml/);
        assert.match(text, /User-agent: GPTBot\nDisallow: \//);
        assert.ok(!text.includes('Disallow: /product'));
      }
    });
  }
}
for (const host of ['aedrova.com', 'www.aedrova.com']) {
  for (const method of ['GET', 'HEAD']) {
    test(`${host} ${method} sitemap survives origin outage`, async () => {
      const response = await handle(new Request(`https://${host}/sitemap.xml`, {method}), () => {throw Error('origin down');});
      assert.equal(response.status, 200);
      assert.match(response.headers.get('content-type'), /application\/xml/);
      assert.equal(await response.text(), method === 'HEAD' ? '' : SITEMAP);
      assert.ok(!SITEMAP.includes('<loc>https://aedrova.com/download</loc>'));
      assert.ok(!SITEMAP.includes('/account'));
    });
  }
}
test('edge exports match the canonical Python discovery metadata', async () => {
  const {execFileSync} = await import('node:child_process');
  const value = JSON.parse(execFileSync('uv', ['run', 'python', '-c',
    'import json; from aedrova_site.config import Config; from aedrova_site.discovery import CANONICAL, robots, sitemap; c=Config(origin=CANONICAL); print(json.dumps([robots(c), sitemap(c)]))'
  ], {encoding:'utf8'}));
  assert.deepEqual([ROBOTS, SITEMAP], value);
  assert.ok(!ROBOTS.includes('Disallow: /download\n'));
  assert.ok(ROBOTS.includes('Disallow: /download/'));
});
test('other paths, hosts and methods pass through unchanged', async () => {
  for (const [url, method] of [
    ['https://aedrova.com/api/session', 'GET'], ['https://aedrova.com/robots.txt/extra', 'GET'],
    ['https://staging.example/robots.txt', 'GET'], ['https://aedrova.com/robots.txt', 'POST'],
    ['https://aedrova.com/auth/callback', 'GET'],
    ['https://aedrova.com/sitemap.xml/private', 'GET'],
    ['https://aedrova.com/sitemap.xml', 'POST'],
    ['https://aedrova.com/download', 'GET']
  ]) {
    const original = new Response('original', {status:403});
    assert.equal(await handle(new Request(url, {method}), async () => original), original);
  }
});
