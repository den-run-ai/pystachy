"""Local content-addressed artifacts with locked misses and manifest-last commit.

This cache is for trusted jobs in a private directory on a local POSIX filesystem.
It is not a network-filesystem lock protocol or an untrusted execution sandbox.
The caller owns the complete semantic key and validates it before every lookup.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def key_for(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def checked_key(key):
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("invalid artifact key")
    return key


def atomic_copy(source, destination):
    destination = Path(destination)
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, Path(source).open("rb") as stream:
            shutil.copyfileobj(stream, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(destination, value):
    destination = Path(destination)
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(canonical(value) + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ArtifactCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("locks", "objects", "entries"):
            path = self.root / name
            if path.is_symlink():
                raise ValueError("cache directories must not be symlinks")
            path.mkdir(exist_ok=True)

    @contextmanager
    def locked(self, key, timeout=600, on_tick=None):
        checked_key(key)
        start = time.monotonic()
        with (self.root / "locks" / key).open("a+b") as lock:
            while True:
                if on_tick is not None:
                    on_tick()
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() - start >= timeout:
                        raise TimeoutError("artifact cache lease acquisition timed out") from None
                    time.sleep(0.01)
            try:
                yield time.monotonic() - start
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def lookup(self, key, *, max_bytes=None):
        """Missing or corrupt entries are misses; never return unchecked bytes."""
        checked_key(key)
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
            raise ValueError("artifact lookup byte bound must be nonnegative")
        try:
            pointer = self.root / "entries" / (key + ".json")
            if pointer.is_symlink() or pointer.stat().st_size > 4096:
                return None
            record = json.loads(pointer.read_bytes())
            if (not isinstance(record, dict) or set(record) != {"version", "key", "sha256", "bytes"}
                    or type(record["version"]) is not int or record["version"] != 1
                    or record["key"] != key or type(record["bytes"]) is not int or record["bytes"] < 0):
                return None
            if max_bytes is not None and record["bytes"] > max_bytes:
                return None
            checked_key(record["sha256"])
            artifact = self.root / "objects" / record["sha256"]
            if (artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size != record["bytes"]
                    or sha256(artifact) != record["sha256"]):
                return None
            return artifact, record
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def publish(self, key, source):
        """Caller holds the key lock; immutable object first, pointer last."""
        checked_key(key)
        digest = sha256(source)
        destination = self.root / "objects" / digest
        fd, temporary = tempfile.mkstemp(prefix="pending-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as output, Path(source).open("rb") as stream:
                shutil.copyfileobj(stream, output)
                output.flush()
                os.fsync(output.fileno())
            if sha256(temporary) != digest:
                raise RuntimeError("artifact changed during cache publication")
            # Validate the private copy before touching a content-addressed name
            # that older successful entries may already reference.
            record = {"version": 1, "key": key, "sha256": digest, "bytes": Path(temporary).stat().st_size}
            os.replace(temporary, destination)
            atomic_json(self.root / "entries" / (key + ".json"), record)
            return record
        finally:
            Path(temporary).unlink(missing_ok=True)
