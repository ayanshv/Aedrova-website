from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from aedrova_site.app import create_app
from aedrova_site.config import Config
from aedrova_site.meetings import issue_meeting_access
from aedrova_site.store import Denied


class Identity:
    def __init__(self):
        self.ids = {key: str(uuid4()) for key in
                    ('meeting_id', 'workspace_id', 'channel_id', 'user_id')}
        self.scope = {**self.ids, 'room_name': 'aedrova-' + '-'.join(self.ids[key] for key in
                            ('workspace_id', 'channel_id', 'meeting_id'))}
        self.requests = []

    def user(self, token):
        return {'id': self.ids['user_id']}

    def request(self, path, token, *, method, data):
        self.requests.append((path, method, data))
        return self.scope


class Store:
    def rate_limit(self, key, limit):
        assert key.startswith('meeting-join:') and limit == 8


def configured():
    return Config(encryption_key=Fernet.generate_key().decode(),
                  meetings_enabled=True, livekit_url='wss://example.livekit.cloud',
                  livekit_api_key='test-media-key', livekit_api_secret='fixture-only-' * 4)


def test_no_credential_when_meetings_are_disabled():
    identity = Identity()
    with pytest.raises(Denied, match='No microphone or camera'):
        issue_meeting_access(Config(), identity, Store(), 'user-token', uuid4())
    assert not identity.requests


def test_backend_mints_only_channel_scoped_short_lived_grants():
    config, identity = configured(), Identity()
    result = issue_meeting_access(config, identity, Store(), 'user-token',
                                  UUID(identity.ids['meeting_id']))
    claims = jwt.decode(result['token'], config.livekit_api_secret,
                        algorithms=['HS256'], issuer=config.livekit_api_key)
    assert claims['sub'] == identity.ids['user_id']
    assert claims['exp'] - claims['nbf'] == 300
    assert claims['video']['room'] == identity.scope['room_name']
    assert claims['video']['roomJoin'] and not claims['video']['canPublishData']
    assert not claims['video'].get('roomAdmin') and not claims['video'].get('roomRecord')
    assert config.livekit_api_secret not in str(result)
    assert config.livekit_api_key not in repr(config)
    assert identity.requests[0][0] == '/rest/v1/rpc/join_meeting'


@pytest.mark.parametrize('field', ['user_id', 'meeting_id', 'room_name'])
def test_rpc_scope_mismatch_is_rejected(field):
    identity = Identity()
    identity.scope[field] = str(uuid4())
    with pytest.raises(Denied):
        issue_meeting_access(configured(), identity, Store(), 'user-token',
                             UUID(identity.ids['meeting_id']))


def test_channel_rls_denial_prevents_token(monkeypatch):
    identity = Identity()
    def forbidden(*args, **kwargs):
        raise Denied('Channel not accessible')
    monkeypatch.setattr(identity, 'request', forbidden)
    with pytest.raises(Denied):
        issue_meeting_access(configured(), identity, Store(), 'user-token', uuid4())


@pytest.mark.parametrize('url', ['ws://example.livekit.cloud', 'wss://user:pass@host',
                                'wss://host/?token=secret'])
def test_config_requires_secure_media_origin(url):
    config = configured()
    config.livekit_url = url
    with pytest.raises(ValueError):
        config.validate()


def test_public_api_stays_closed_without_media_acceptance(tmp_path):
    app = create_app(Config(database=f'sqlite:///{tmp_path}/test.sqlite3'))
    with TestClient(app) as client:
        result = client.post('/api/meetings/join', json={'meeting': str(uuid4())},
                             headers={'Authorization': 'Bearer test-token'})
        assert result.status_code == 403
        assert 'being prepared' in result.json()['error']
    app.state.store.engine.dispose()
