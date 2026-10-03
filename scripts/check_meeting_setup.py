"""Credential-safe meeting staging preflight; optional public HTTPS readiness probe.

Does not join rooms, capture media, transcribe, purchase, deploy or print configuration.
Run in the server environment, with private values injected by its secret store.
"""

import argparse
import json

import httpx

from aedrova_site.config import Config


def check(config, *, probe=False, client=None):
    config.validate()
    if not config.production or not config.meetings_enabled:
        raise ValueError('Use enabled production-mode meeting staging configuration.')
    if config.checkout_enabled or config.gateway_enabled or config.release_ready:
        raise ValueError('Meeting staging must keep paid AI, checkout and releases disabled.')
    if probe:
        owned = client is None
        client = client or httpx.Client(timeout=10, follow_redirects=False)
        try:
            for path in ('/health', '/health/meetings'):
                with client.stream('GET', config.origin.rstrip('/') + path) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 16384:
                            raise ValueError('Unexpected readiness response.')
                    result = json.loads(body)
                expected = 'ok' if path == '/health' else 'ready'
                if result.get('status') != expected:
                    raise ValueError('The shared meeting service is not ready.')
        finally:
            if owned:
                client.close()
    return {'configuration': 'passed', 'https_readiness': 'passed' if probe else 'not tested',
            'two_mac_media': 'not tested', 'transcription': 'not enabled'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    try:
        report = check(Config.load(), probe=args.probe)
    except Exception:
        # Config/HTTP/SQL error payloads can contain keys, origins or DSNs.
        raise SystemExit('Meeting staging preflight failed. Check server configuration, '
                         'HTTPS and the independent guard; credentials were not printed.') from None
    print(json.dumps(report))


if __name__ == '__main__':
    main()
