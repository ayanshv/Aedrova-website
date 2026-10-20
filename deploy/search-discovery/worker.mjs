import { ROBOTS } from './robots.mjs';

export async function handle(request, upstream = fetch) {
  const url = new URL(request.url);
  if (!['aedrova.com', 'www.aedrova.com'].includes(url.hostname)
      || url.pathname !== '/robots.txt' || !['GET', 'HEAD'].includes(request.method)) {
    return upstream(request);
  }
  return new Response(request.method === 'HEAD' ? null : ROBOTS, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=300', 'X-Content-Type-Options': 'nosniff' }
  });
}
export default { fetch(request) { return handle(request); } };
