import { ROBOTS, SITEMAP } from './robots.mjs';

export async function handle(request, upstream = fetch) {
  const url = new URL(request.url);
  if (!['aedrova.com', 'www.aedrova.com'].includes(url.hostname)
      || !['/robots.txt', '/sitemap.xml'].includes(url.pathname)
      || !['GET', 'HEAD'].includes(request.method)) {
    return upstream(request);
  }
  const isRobots = url.pathname === '/robots.txt';
  return new Response(request.method === 'HEAD' ? null : (isRobots ? ROBOTS : SITEMAP), {
    headers: { 'Content-Type': isRobots ? 'text/plain; charset=utf-8' : 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=300', 'X-Content-Type-Options': 'nosniff' }
  });
}
export default { fetch(request) { return handle(request); } };
