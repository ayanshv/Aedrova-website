"""Self-contained browser errors, exportable for an independent edge fallback."""

import base64
import hashlib
from functools import lru_cache
from html import escape
from http import HTTPStatus
from pathlib import Path

from starlette.responses import HTMLResponse, JSONResponse

from aedrova_site.observability import emit

ROOT = Path(__file__).parent
STYLE = """
:root{color-scheme:light dark;
--bg:#f5f6f8;
--text:#20242c;
--muted:#667180;
--blue:#246bfd;
--line:#e0e4ec}
*{box-sizing:border-box}
body{margin:0;
background:var(--bg);
color:var(--text);
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased}
header,footer{max-width:1160px;
margin:auto;
padding:30px 28px;
display:flex;
justify-content:space-between;
align-items:center}
a{color:inherit;
text-decoration:none}
header a{font-size:22px;
font-weight:650;
letter-spacing:-.7px}
header span{color:var(--muted);
font-size:13px}
main{min-height:70vh;
max-width:780px;
margin:auto;
padding:70px 28px 90px;
text-align:center}
.scene{height:185px;
position:relative;
margin:auto auto 32px;
max-width:360px}
.bud{position:absolute;
width:170px;
height:170px;
background-image:var(--atlas);
background-size:300% 200%;
background-position:0 0;
left:38px;
top:10px;
transform:rotate(-8deg)}
.bud.small{width:110px;
height:110px;
background-position:100% 0;
left:auto;
right:20px;
top:65px;
transform:rotate(12deg)}
.code{font-size:12px;
letter-spacing:.15em;
color:var(--muted);
font-weight:600}
h1{font-size:clamp(34px,6vw,56px);
line-height:1.07;
letter-spacing:-.045em;
margin:20px 0;
font-weight:650}
p{max-width:510px;
margin:0 auto;
color:var(--muted);
font-size:16px;
line-height:1.65}
.actions{display:flex;
justify-content:center;
gap:20px;
align-items:center;
margin:32px 0;
flex-wrap:wrap}
.primary{background:var(--blue);
color:white;
padding:15px 25px;
border-radius:12px;
font-size:14px;
font-weight:600;
transition:transform .15s}
.primary:hover{transform:translateY(-2px)}
.primary:active{transform:scale(.98)}
.secondary{font-size:14px}
a:focus-visible{outline:3px solid var(--blue);
outline-offset:5px}
.note{font-size:12px}
footer{border-top:1px solid var(--line);
font-size:12px;
color:var(--muted);
gap:20px;
flex-wrap:wrap}
footer nav{display:flex;
gap:24px}
@media(prefers-color-scheme:dark){:root{--bg:#18191c;
--text:#f5f6f8;
--muted:#a4acb8;
--line:#303238;
--blue:#397dff}
}
@media(max-width:500px){header,footer{padding:24px}
main{padding-top:35px}
header span{display:none}
.scene{transform:scale(.9);
margin-bottom:10px}
}
@media(prefers-reduced-motion:reduce){.primary{transition:none}
}

"""


@lru_cache(maxsize=1)
def atlas_url():
    return (
        "data:image/png;base64,"
        + base64.b64encode((ROOT / "static" / "buds-atlas.png").read_bytes()).decode()
    )


@lru_cache(maxsize=64)
def error_html(status):
    status = int(status)
    if status == 404:
        title, copy = (
            "A little off course.",
            "This page may have moved, or the link may be incomplete. Your Buds will "
            "meet you back at home.",
        )
    elif status in {401, 403}:
        title, copy = (
            "This space needs permission.",
            "Try signing in with the account that has access. If this seems unexpected, "
            "we're here to help.",
        )
    elif status == 429:
        title, copy = (
            "A moment to catch our breath.",
            "There have been too many requests. Wait a moment, then try again.",
        )
    elif status >= 500:
        title, copy = (
            "We’ll be right back.",
            "Aedrova is temporarily unavailable. We’re working to get things back up. "
            "Please try again shortly.",
        )
    else:
        title, copy = (
            "Let’s try that again.",
            "We couldn't open this page. Check the link and try again, or get in touch "
            "so we can help.",
        )
    try:
        reason = HTTPStatus(status).phrase
    except ValueError:
        reason = "Connection interrupted"
    style = STYLE + "\n.bud{background-image:url('" + atlas_url() + "')}"
    action = "Back to home" if status == 404 else "Try again"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Aedrova | {escape(title)}</title>
<style>{style}</style>
</head>
<body>
<header>
<a href="/" aria-label="Aedrova home">✦ Aedrova</a>
<span>Your team, plus AI.</span>
</header>
<main>
<div class="scene" aria-hidden="true">
<div class="bud">
</div>
<div class="bud small">
</div>
</div>
<div class="code">{status} · {escape(reason)}</div>
<h1>{escape(title)}</h1>
<p>{escape(copy)}</p>
<div class="actions">
<a class="primary" href="/">{action}</a>
<a class="secondary" href="mailto:contact@aedrova.com">Contact support ↗</a>
</div>
<p class="note">No need to change your account or reconnect your tools.</p>
</main>
<footer>
<span>Aedrova · Your team. Your tools. Together.</span>
<nav>
<a href="/privacy">Privacy</a>
<a href="/terms">Terms</a>
</nav>
</footer>
</body>
</html>"""


def error_response(status, headers=None):
    html = error_html(status)
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    digest = base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
    return HTMLResponse(
        html,
        status_code=status,
        headers={
            **(headers or {}),
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; style-src "
            f"'sha256-{digest}'; img-src data:; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'none'",
        },
    )


class BrowserErrors:
    """Keep API contracts intact; replace browser navigation errors at the boundary."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        browser = (
            scope["type"] == "http"
            and scope.get("method") == "GET"
            and b"text/html" in headers.get(b"accept", b"")
            and not scope.get("path", "").startswith(("/api/", "/gateway/", "/static/", "/stripe/"))
        )
        if not browser:
            # Keep JSON/API errors bounded and private even for unexpected failures.
            sent = False

            async def machine_response(message):
                nonlocal sent
                if message["type"] == "http.response.start":
                    sent = True
                await send(message)

            try:
                return await self.app(scope, receive, machine_response)
            except Exception as exc:
                if sent:
                    raise
                emit("service_failure", category=type(exc).__name__)
                return await JSONResponse(
                    {"error": "The service could not complete this request. Retry shortly."},
                    status_code=500,
                )(scope, receive, send)
        started = False
        replaced = False

        async def branded(message):
            nonlocal started, replaced
            if message["type"] == "http.response.start":
                started = True
                if message["status"] >= 400:
                    replaced = True
                    retained = {
                        k.decode(): v.decode()
                        for k, v in message.get("headers", [])
                        if k.lower() in {b"retry-after", b"strict-transport-security"}
                    }
                    await error_response(message["status"], retained)(scope, receive, send)
                    return
            if not replaced:
                await send(message)

        try:
            await self.app(scope, receive, branded)
        except Exception as exc:
            if started:
                raise
            emit("website_failure", category=type(exc).__name__)
            await error_response(500)(scope, receive, send)
