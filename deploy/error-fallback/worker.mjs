import { HTML, HEADERS } from './fallback.mjs';

export function isPage(request) {
  const path = new URL(request.url).pathname;
  return request.method === 'GET' && request.headers.get('accept')?.includes('text/html')
    && !['/api/', '/gateway/', '/static/', '/stripe/'].some(prefix => path.startsWith(prefix));
}
export function fallback(status = 503, retryAfter = '30') {
  return new Response(HTML.replace('503 · Service Unavailable', `${status} · Temporarily unavailable`), {
    status, headers: { ...HEADERS, 'Retry-After': retryAfter }
  });
}
export async function handle(request, upstream = fetch) {
  if (!isPage(request)) return upstream(request);
  try {
    const response = await upstream(request);
    if (response.status >= 500) {
      await response.body?.cancel();
      return fallback(response.status, response.headers.get('retry-after') || '30');
    }
    return response;
  } catch {
    return fallback();
  }
}
export default { fetch(request) { return handle(request); } };
