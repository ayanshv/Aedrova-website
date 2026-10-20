import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handle } from './worker.mjs';
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
test('other paths, hosts and methods pass through unchanged', async () => {
  for (const [url, method] of [
    ['https://aedrova.com/api/session', 'GET'], ['https://aedrova.com/robots.txt/extra', 'GET'],
    ['https://staging.example/robots.txt', 'GET'], ['https://aedrova.com/robots.txt', 'POST'],
    ['https://aedrova.com/auth/callback', 'GET']
  ]) {
    const original = new Response('original', {status:403});
    assert.equal(await handle(new Request(url, {method}), async () => original), original);
  }
});
