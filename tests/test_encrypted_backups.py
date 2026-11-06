import io
import json
import os
import sqlite3
import tarfile

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from aedrova_site.backup_bundle import MAGIC, MANIFEST, create, init_key, private_key, restore
from aedrova_site.store import Store


def inputs(tmp_path):
    source = tmp_path / "snapshot"
    source.mkdir()
    key = tmp_path / "backup.key"
    init_key(key)
    bundle = tmp_path / "snapshot.aedrovabackup"
    return source, key, bundle


def test_encrypted_round_trip_restores_money_sessions_and_storage_bytes(tmp_path):
    source, key, bundle = inputs(tmp_path)
    application_key = Fernet.generate_key().decode()
    active = tmp_path / "active.sqlite"
    store = Store("sqlite:///" + str(active), encryption_key=application_key, free_enabled=True)
    store.activate_free("owner", "workspace")
    store.session("session", {"access_token": "synthetic-private-session"})
    run = store.run(store.create_run("owner", "workspace", "codex", "request-1234")["token"])
    request, _ = store.reserve(run, "inference-1234", 100)
    store.settle(request, 75, b"synthetic-answer")
    before = store.balance("workspace")
    with sqlite3.connect(active) as origin, sqlite3.connect(source / "database.sqlite") as target:
        origin.backup(target)
    store.engine.dispose()
    files = source / "storage" / "workspace"
    files.mkdir(parents=True)
    (files / "voice.wav").write_bytes(b"RIFF-synthetic-private-audio")
    created = create(source, bundle, key)
    assert created["files"] == 2
    assert b"synthetic-private-session" not in bundle.read_bytes()
    assert b"RIFF-synthetic-private-audio" not in bundle.read_bytes()
    recovered = tmp_path / "restored"
    assert restore(bundle, recovered, key)["files"] == 2
    assert (recovered / "storage/workspace/voice.wav").read_bytes() == (
        files / "voice.wav"
    ).read_bytes()
    recovered_store = Store(
        "sqlite:///" + str(recovered / "database.sqlite"),
        encryption_key=application_key,
        free_enabled=True,
    )
    try:
        assert recovered_store.balance("workspace") == before
        assert recovered_store.session("session")["access_token"] == "synthetic-private-session"
        recovered_store.settle(request, 75, b"synthetic-answer")
        assert recovered_store.balance("workspace") == before
    finally:
        recovered_store.engine.dispose()
    if os.name != "nt":
        assert bundle.stat().st_mode & 0o077 == 0
        assert (recovered / "database.sqlite").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("damage", ["key", "ciphertext", "truncate"])
def test_failed_authentication_never_publishes_restored_files(tmp_path, damage):
    source, key, bundle = inputs(tmp_path)
    (source / "data.sql").write_text("sensitive fixture")
    create(source, bundle, key)
    if damage == "key":
        key = tmp_path / "wrong.key"
        init_key(key)
    else:
        data = bytearray(bundle.read_bytes())
        if damage == "truncate":
            data = data[:-8]
        else:
            data[len(MAGIC) + 20] ^= 1
        bundle.write_bytes(data)
    destination = tmp_path / "restore"
    with pytest.raises((InvalidTag, ValueError)):
        restore(bundle, destination, key)
    assert not destination.exists()
    assert not list(tmp_path.glob(".aedrova-restore-*"))


def test_no_overwrite_key_capture_symlinks_or_oversized_inputs(tmp_path):
    source, key, bundle = inputs(tmp_path)
    (source / "data.sql").write_text("original")
    create(source, bundle, key)
    original = bundle.read_bytes()
    with pytest.raises(FileExistsError):
        create(source, bundle, key)
    assert bundle.read_bytes() == original
    with pytest.raises(ValueError):
        create(source, source / "invalid", key)
    with pytest.raises(ValueError):
        create(source, tmp_path / "oversized", key, maximum=1)
    with pytest.raises(FileExistsError):
        init_key(key)
    with pytest.raises(ValueError):
        restore(bundle, source, key)
    assert (source / "data.sql").read_text() == "original"
    (source / "alias").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        create(source, tmp_path / "symlink", key)


def malicious_bundle(bundle, key, name, *, link=False, wrong_hash=False):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        entry = tarfile.TarInfo(name)
        if link:
            entry.type, entry.linkname = tarfile.SYMTYPE, "/tmp"
            archive.addfile(entry)
        else:
            entry.size = 4
            archive.addfile(entry, io.BytesIO(b"data"))
        manifest = json.dumps(
            {
                "version": 1,
                "files": [{"name": name, "bytes": 4, "sha256": "wrong" if wrong_hash else ""}],
            }
        ).encode()
        entry = tarfile.TarInfo(MANIFEST)
        entry.size = len(manifest)
        archive.addfile(entry, io.BytesIO(manifest))
    nonce = os.urandom(12)
    header = MAGIC + nonce
    cipher = Cipher(algorithms.AES(private_key(key)), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(header)
    encrypted = cipher.update(data.getvalue()) + cipher.finalize()
    bundle.write_bytes(header + encrypted + cipher.tag)


@pytest.mark.parametrize("name", ["../escape", "/escape", "a/../../escape", "C:\\escape"])
def test_authenticated_archive_cannot_traverse_paths(tmp_path, name):
    _, key, bundle = inputs(tmp_path)
    malicious_bundle(bundle, key, name)
    with pytest.raises(ValueError):
        restore(bundle, tmp_path / "recovered", key)
    assert not (tmp_path / "recovered").exists()
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("link", [True, False])
def test_links_and_hash_mismatches_are_rejected(tmp_path, link):
    _, key, bundle = inputs(tmp_path)
    malicious_bundle(bundle, key, "file", link=link, wrong_hash=True)
    with pytest.raises(ValueError):
        restore(bundle, tmp_path / "recovered", key)
    assert not (tmp_path / "recovered").exists()
