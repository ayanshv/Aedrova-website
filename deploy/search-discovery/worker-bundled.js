const ROBOTS = "User-agent: *\nDisallow: /api/\nDisallow: /dots/\nDisallow: /buds/\nDisallow: /gateway/\nDisallow: /unsubscribe\nDisallow: /auth/\nDisallow: /account\nDisallow: /welcome\nDisallow: /onboarding\nDisallow: /download\nDisallow: /health\nDisallow: /docs\nDisallow: /redoc\nDisallow: /openapi.json\n\nUser-agent: OAI-SearchBot\nDisallow: /api/\nDisallow: /dots/\nDisallow: /buds/\nDisallow: /gateway/\nDisallow: /unsubscribe\nDisallow: /auth/\nDisallow: /account\nDisallow: /welcome\nDisallow: /onboarding\nDisallow: /download\nDisallow: /health\nDisallow: /docs\nDisallow: /redoc\nDisallow: /openapi.json\n\nUser-agent: ChatGPT-User\nDisallow: /api/\nDisallow: /dots/\nDisallow: /buds/\nDisallow: /gateway/\nDisallow: /unsubscribe\nDisallow: /auth/\nDisallow: /account\nDisallow: /welcome\nDisallow: /onboarding\nDisallow: /download\nDisallow: /health\nDisallow: /docs\nDisallow: /redoc\nDisallow: /openapi.json\n\nUser-agent: Claude-SearchBot\nDisallow: /api/\nDisallow: /dots/\nDisallow: /buds/\nDisallow: /gateway/\nDisallow: /unsubscribe\nDisallow: /auth/\nDisallow: /account\nDisallow: /welcome\nDisallow: /onboarding\nDisallow: /download\nDisallow: /health\nDisallow: /docs\nDisallow: /redoc\nDisallow: /openapi.json\n\nUser-agent: Claude-User\nDisallow: /api/\nDisallow: /dots/\nDisallow: /buds/\nDisallow: /gateway/\nDisallow: /unsubscribe\nDisallow: /auth/\nDisallow: /account\nDisallow: /welcome\nDisallow: /onboarding\nDisallow: /download\nDisallow: /health\nDisallow: /docs\nDisallow: /redoc\nDisallow: /openapi.json\n\nUser-agent: Google-Extended\nDisallow: /api/\nDisallow: /dots/\nDisallow: /buds/\nDisallow: /gateway/\nDisallow: /unsubscribe\nDisallow: /auth/\nDisallow: /account\nDisallow: /welcome\nDisallow: /onboarding\nDisallow: /download\nDisallow: /health\nDisallow: /docs\nDisallow: /redoc\nDisallow: /openapi.json\n\nUser-agent: GPTBot\nDisallow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n\nSitemap: https://aedrova.com/sitemap.xml\n";



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
