"""Private encrypted backup bundles; unpack only into a new isolated directory."""

import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"AEDROVA-BACKUP-1\n"
CHUNK = 1024 * 1024
MAXIMUM = 2 * 1024 * 1024 * 1024
MANIFEST = ".aedrova-backup.json"


def private_key(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Use a private regular key file")
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Backup key permissions must be 600 or stricter")
    key = base64.urlsafe_b64decode(path.read_bytes().strip())
    if len(key) != 32:
        raise ValueError("A 256-bit backup key is required")
    return key


def init_key(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(base64.urlsafe_b64encode(os.urandom(32)) + b"\n")


def safe_name(name):
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
        or str(path) != name
        or name == "."
    ):
        raise ValueError("Unsafe backup entry")
    return path


class EncryptedWriter:
    def __init__(self, output, encryptor, maximum):
        self.output, self.encryptor, self.maximum = output, encryptor, maximum
        self.size = 0

    def write(self, data):
        self.size += len(data)
        if self.size > self.maximum:
            raise ValueError("Backup exceeds the configured size bound")
        self.output.write(self.encryptor.update(data))
        return len(data)


def create(source, destination, key_file, *, maximum=MAXIMUM):
    source, destination, key_file = map(Path, (source, destination, key_file))
    root = source.resolve(strict=True)
    if source.is_symlink() or not root.is_dir():
        raise ValueError("Choose a regular backup input directory")
    if root in key_file.resolve().parents or root in destination.resolve().parents:
        raise ValueError("Keep the backup key and output outside the input directory")
    key = private_key(key_file)
    files = sorted(path for path in root.rglob("*") if not path.is_dir() or path.is_symlink())
    if not files or len(files) > 20000:
        raise ValueError("Backup input must contain 1 to 20000 files")
    records, total = [], 0
    for path in files:
        name = path.relative_to(root).as_posix()
        safe_name(name)
        if path.is_symlink() or not path.is_file() or name == MANIFEST:
            raise ValueError("Backup input must contain regular files only")
        total += path.stat().st_size
    if total > maximum:
        raise ValueError("Backup input exceeds the configured size bound")
    descriptor, temporary = tempfile.mkstemp(prefix=".aedrova-backup-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            nonce = os.urandom(12)
            header = MAGIC + nonce
            output.write(header)
            encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            encryptor.authenticate_additional_data(header)
            writer = EncryptedWriter(output, encryptor, maximum + 16 * CHUNK)
            with tarfile.open(fileobj=writer, mode="w|") as archive:
                for path in files:
                    name = path.relative_to(root).as_posix()
                    before = path.stat()
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        while data := stream.read(CHUNK):
                            digest.update(data)
                        stream.seek(0)
                        info = tarfile.TarInfo(name)
                        info.size, info.mode = before.st_size, 0o600
                        archive.addfile(info, stream)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError("Backup input changed while reading; take a new snapshot")
                    records.append(
                        {"name": name, "bytes": before.st_size, "sha256": digest.hexdigest()}
                    )
                encoded = json.dumps({"version": 1, "files": records}).encode()
                if len(encoded) > 4 * CHUNK:
                    raise ValueError("Backup manifest exceeds the configured bound")
                info = tarfile.TarInfo(MANIFEST)
                info.size, info.mode = len(encoded), 0o600
                archive.addfile(info, io.BytesIO(encoded))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {
        "files": len(records),
        "plaintext_bytes": total,
        "encrypted_bytes": destination.stat().st_size,
    }


def restore(bundle, destination, key_file, *, maximum=MAXIMUM):
    bundle, destination, key_file = map(Path, (bundle, destination, key_file))
    key = private_key(key_file)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Restore destination must not already exist")
    size = bundle.stat().st_size
    if size > maximum + 16 * CHUNK or size < len(MAGIC) + 28:
        raise ValueError("Invalid encrypted backup size")
    with tempfile.TemporaryDirectory(prefix=".aedrova-restore-", dir=destination.parent) as temp:
        folder = Path(temp)
        plaintext = folder / "authenticated.tar"
        with bundle.open("rb") as source, plaintext.open("xb") as output:
            plaintext.chmod(0o600)
            header = source.read(len(MAGIC) + 12)
            if not header.startswith(MAGIC):
                raise ValueError("Unknown backup format")
            source.seek(-16, os.SEEK_END)
            tag = source.read(16)
            source.seek(len(header))
            decryptor = Cipher(algorithms.AES(key), modes.GCM(header[-12:], tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            remaining = size - len(header) - 16
            while remaining:
                data = source.read(min(CHUNK, remaining))
                if not data:
                    raise ValueError("Truncated backup")
                remaining -= len(data)
                output.write(decryptor.update(data))
            output.write(decryptor.finalize())
        recovered = folder / "verified"
        recovered.mkdir(mode=0o700)
        seen, manifest, total = {}, None, 0
        with tarfile.open(plaintext, mode="r:") as archive:
            for index, entry in enumerate(archive):
                name = entry.name
                safe_name(name)
                if index > 20000 or not entry.isfile() or name in seen:
                    raise ValueError("Invalid or duplicate backup entry")
                total += entry.size
                if entry.size < 0 or total > maximum + 4 * CHUNK:
                    raise ValueError("Restored data exceeds the configured bound")
                content = archive.extractfile(entry)
                if name == MANIFEST:
                    if manifest is not None or entry.size > 4 * CHUNK:
                        raise ValueError("Invalid backup manifest")
                    manifest = json.load(content)
                    continue
                target = recovered.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest, length = hashlib.sha256(), 0
                with target.open("xb") as output:
                    target.chmod(0o600)
                    while data := content.read(CHUNK):
                        length += len(data)
                        digest.update(data)
                        output.write(data)
                seen[name] = {"name": name, "bytes": length, "sha256": digest.hexdigest()}
        if (
            not isinstance(manifest, dict)
            or manifest.get("version") != 1
            or not isinstance(manifest.get("files"), list)
        ):
            raise ValueError("Missing backup manifest")
        expected = manifest["files"]
        if len(expected) != len(seen) or any(
            not isinstance(row, dict) or seen.get(row.get("name")) != row for row in expected
        ):
            raise ValueError("Backup content does not match its manifest")
        if destination.exists() or destination.is_symlink():
            raise ValueError("Restore destination already exists")
        destination.mkdir(mode=0o700)
        try:
            for item in recovered.iterdir():
                item.rename(destination / item.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
        return {"files": len(seen), "plaintext_bytes": sum(row["bytes"] for row in seen.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init-key", "create", "restore"])
    parser.add_argument("--key-file", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "init-key":
            init_key(args.key_file)
            result = {"status": "private key created; keep separately from backups"}
        elif not args.source or not args.destination:
            parser.error("--source and --destination are required")
        else:
            result = (create if args.action == "create" else restore)(
                args.source, args.destination, args.key_file
            )
        print(json.dumps(result))
    except Exception:
        raise SystemExit(
            "Backup operation failed. Check private paths, key and input integrity."
        ) from None


if __name__ == "__main__":
    main()
