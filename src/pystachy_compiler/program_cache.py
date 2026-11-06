"""Opt-in complete-program cache; the driver supplies the compilation identity.

Source reads and import-resolution probes are recorded at the point the loader
uses them, including its unsuccessful probes. They survive inference retries.
The manifest becomes visible only after its complete executable is in place.
This is a private, same-user cache: FNV detects accidental corruption, not hostile
modifications by the user who can already replace the compiler or the program.
"""
from __future__ import annotations
import os
import tempfile
import time
from src.pystachy_compiler.diagnostics import RAW


MAGIC = "pystachy-program-cache-1\n"
MEMO_MAGIC = "pystachy-static-hashes-1\n"
MAX_MANIFEST = 8 * 1024 * 1024
MAX_FIELDS = 65536
MAX_BINARY = 512 * 1024 * 1024
ACTIVE: list[bool] = [False]
VALID: list[bool] = [True]
SOURCES: dict[str, str] = {}
PROBES: dict[str, str] = {}
STATICS: dict[str, str] = {}
# Canonical paths deduplicate a shared library reached from several LLVM tools.
# Only snapshots whose timestamps were already settled enter this memo.
STATIC_MEMO: dict[str, str] = {}
MEMO_ROOT: list[str] = [""]


def fnv(s: str) -> str:
    # FNV-1a, 64 bits wide, in two halves so no product overflows a signed i64.
    hi = 0xCBF29CE4
    lo = 0x84222325
    for c in s:
        lo ^= ord(c)
        m = lo * 0x1B3
        hi = (hi * 0x1B3 + (lo << 8) + (m >> 32)) & 0xFFFFFFFF
        lo = m & 0xFFFFFFFF
    return f"{hi:08x}{lo:08x}"


def _q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def _sh(cmd: str) -> bool:
    return os.system("{ " + cmd + "; } > /dev/null 2>&1") == 0


def _stat3(path: str) -> str:
    try:
        return f"{os.path.getsize(path)} {os.path.getmtime(path)} {os.path.getctime(path)}"
    except (OSError, ValueError):
        return ""


def _settled(st: str) -> bool:
    fields = st.split(" ")
    try:
        return len(fields) == 3 and time.time() - max(float(fields[1]), float(fields[2])) > 2
    except ValueError:
        return False


def _pack(fields: list[str]) -> str:
    # Lengths, rather than delimiter escaping, preserve every legal path spelling.
    return "".join([f"{len(s)}:{s}" for s in fields])


def _unpack(text: str) -> list[str]:
    fields: list[str] = []
    at = 0
    while at < len(text):
        colon = text.find(":", at)
        if colon <= at or colon - at > 7 or len(fields) >= MAX_FIELDS:
            return []
        digits = text[at:colon]
        for c in digits:
            if c < "0" or c > "9":
                return []
        size = int(digits)
        end = colon + 1 + size
        if size > MAX_MANIFEST or end > len(text):
            return []
        fields.append(text[colon + 1:end])
        at = end
    return fields


def _read(path: str, limit: int, encoding: str) -> tuple[bool, str]:
    try:
        # Never block on a FIFO substituted for a cache entry or dependency.
        if not os.path.isfile(path) or (limit > 0 and os.path.getsize(path) > limit):
            return (False, "")
        f = open(path, "r", encoding=encoding, newline="")
        try:
            text = f.read(limit + 1) if limit > 0 else f.read()
        finally:
            f.close()
        if limit > 0 and len(text) > limit:
            return (False, "")
        return (True, text)
    except (OSError, ValueError):
        return (False, "")


def _file_hash(path: str) -> str:
    # LLVM shared libraries can exceed 100 MiB. Hash in bounded chunks without
    # keeping another complete copy in the compiler's heap.
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_BINARY:
            return ""
        hi = 0xCBF29CE4
        lo = 0x84222325
        total = 0
        f = open(path, "r", encoding=RAW, newline="")
        try:
            while True:
                text = f.read(65536)
                if text == "":
                    break
                total += len(text)
                if total > MAX_BINARY:
                    return ""
                for c in text:
                    lo ^= ord(c)
                    m = lo * 0x1B3
                    hi = (hi * 0x1B3 + (lo << 8) + (m >> 32)) & 0xFFFFFFFF
                    lo = m & 0xFFFFFFFF
        finally:
            f.close()
        return f"{hi:08x}{lo:08x}"
    except (OSError, ValueError):
        return ""


def start() -> None:
    SOURCES.clear()
    PROBES.clear()
    STATICS.clear()
    VALID[0] = True
    ACTIVE[0] = True


def stop() -> None:
    ACTIVE[0] = False


def _record(table: dict[str, str], path: str, snapshot: str) -> None:
    if "\0" in path or snapshot == "" or (path in table and table[path] != snapshot):
        VALID[0] = False
    else:
        table[path] = snapshot


def tracked_exists(path: str) -> bool:
    result = os.path.exists(path)
    if ACTIVE[0]:
        try:
            _record(PROBES, path, _pack(["1" if result else "0", os.path.realpath(path)]))
        except (OSError, ValueError):
            VALID[0] = False
    return result


def track_source(path: str, text: str) -> None:
    if ACTIVE[0]:
        try:
            _record(SOURCES, path, _pack([os.path.realpath(path), fnv(text)]))
        except (OSError, ValueError):
            VALID[0] = False


def _source_matches(path: str, snapshot: str) -> bool:
    fields = _unpack(snapshot)
    if len(fields) != 2 or os.path.realpath(path) != fields[0]:
        return False
    read = _read(path, 0, RAW)
    # The loader consumes universal-newline text. Hash exactly that text, including
    # empty files, rather than trusting stat information or rereading during capture.
    return read[0] and fnv(read[1].replace("\r\n", "\n").replace("\r", "\n")) == fields[1]


def _probe_matches(path: str, snapshot: str) -> bool:
    fields = _unpack(snapshot)
    return (len(fields) == 2 and fields[0] in ["0", "1"]
            and os.path.exists(path) == (fields[0] == "1") and os.path.realpath(path) == fields[1])


def _static_matches(path: str, snapshot: str) -> bool:
    fields = _unpack(snapshot)
    if len(fields) != 4 or fields[3] not in ["0", "1"]:
        return False
    if os.path.realpath(path) != fields[0] or _stat3(path) != fields[1] or fields[1] == "":
        return False
    # A timestamp may be trusted only if it was settled when the bytes were read.
    # A racy capture remains content-checked even after its timestamp grows older.
    return fields[3] == "1" or (_file_hash(path) == fields[2] and _stat3(path) == fields[1])


def track_static(path: str) -> None:
    if not ACTIVE[0]:
        return
    try:
        real = os.path.realpath(path)
        st = _stat3(path)
        snapshot = STATIC_MEMO.get(real, "")
        if snapshot == "" or not _static_matches(path, snapshot):
            digest = _file_hash(path)
            if digest == "" or st == "" or _stat3(path) != st or os.path.realpath(path) != real:
                VALID[0] = False
                return
            settled = "1" if _settled(st) else "0"
            snapshot = _pack([real, st, digest, settled])
            if settled == "1":
                STATIC_MEMO[real] = snapshot
        _record(STATICS, path, snapshot)
    except (OSError, ValueError):
        VALID[0] = False


def _safe_dir(path: str, private: bool) -> bool:
    p = _q(path)
    # Linux prototype: GNU stat supplies the mode; the shell checks ownership.
    # Do not repair unsafe directories, since they may belong to another use.
    mode = f'[ "$(stat -c %a -- {p})" = 700 ]' if private else f'm=$(stat -c %a -- {p}) && [ "$((0$m & 022))" = 0 ]'
    return _sh(f"[ -d {p} ] && [ ! -L {p} ] && [ -O {p} ] && {mode}")


def _no_symlink_dirs(path: str) -> bool:
    prefix = "/" if path.startswith("/") else ""
    for part in path.split("/"):
        if part != "":
            prefix += ("" if prefix == "" or prefix.endswith("/") else "/") + part
            if os.path.islink(prefix):
                return False
    return True


def _cache_dir(cache_root: str) -> str:
    try:
        if cache_root == "" or "\0" in cache_root:
            return ""
        base = cache_root.rstrip("/") or "/"
        if not _no_symlink_dirs(base):
            return ""
        if not os.path.exists(base) and not _sh("mkdir -p -- " + _q(base)):
            return ""
        if not _safe_dir(base, False):
            return ""
        root = base + "/program-v1"
        if not os.path.lexists(root):
            try:
                os.mkdir(root, 0o700)
            except OSError:
                pass  # another writer may have created it
        return root if _safe_dir(root, True) else ""
    except (OSError, ValueError):
        return ""


def _hex(s: str) -> bool:
    if len(s) != 16:
        return False
    for c in s:
        if c not in "0123456789abcdef":
            return False
    return True


def _regular(path: str) -> bool:
    return os.path.isfile(path) and not os.path.islink(path)


def _document(path: str, magic: str) -> list[str]:
    if not _regular(path):
        return []
    read = _read(path, MAX_MANIFEST, "utf-8")
    text = read[1]
    if not read[0] or not text.startswith(magic) or len(text) < len(magic) + 17:
        return []
    digest = text[len(magic):len(magic) + 16]
    payload = text[len(magic) + 17:]
    if text[len(magic) + 16] != "\n" or not _hex(digest) or fnv(payload) != digest:
        return []
    return _unpack(payload)


def _load_memo(root: str) -> None:
    if MEMO_ROOT[0] == root:
        return
    MEMO_ROOT[0] = root
    fields = _document(root + "/static-hashes", MEMO_MAGIC)
    if len(fields) % 2 != 0:
        return
    for i in range(0, len(fields), 2):
        real = fields[i]
        snapshot = fields[i + 1]
        parts = _unpack(snapshot)
        if (len(parts) == 4 and real == parts[0] and "\0" not in real
                and _hex(parts[2]) and parts[3] == "1"):
            # track_static verifies the canonical path and all three stat fields
            # before reusing a memo. Loading it never validates a source read.
            STATIC_MEMO[real] = snapshot


def _save_memo(root: str, stage: str) -> None:
    try:
        fields: list[str] = []
        for real in sorted(STATIC_MEMO):
            fields.extend([real, STATIC_MEMO[real]])
        payload = _pack(fields)
        text = MEMO_MAGIC + fnv(payload) + "\n" + payload
        if len(text) > MAX_MANIFEST or len(fields) > MAX_FIELDS:
            return
        part = stage + "/memo"
        f = open(part, "w", encoding="utf-8", newline="")
        try:
            f.write(text)
        finally:
            f.close()
        # Concurrent writers may forget each other's new memos, costing only a
        # rehash. No reader can see a half-written snapshot.
        os.replace(part, root + "/static-hashes")
    except (OSError, ValueError):
        pass  # the shared hash memo is optional, including on a read-only cache


def _valid_records(fields: list[str]) -> bool:
    if len(fields) < 5 or (len(fields) - 2) % 3 != 0:
        return False
    sources = 0
    seen: dict[str, bool] = {}
    for i in range(2, len(fields), 3):
        kind = fields[i]
        path = fields[i + 1]
        snapshot = fields[i + 2]
        key = _pack([kind, path])
        if "\0" in path or key in seen:
            return False
        seen[key] = True
        if kind == "source":
            if not _source_matches(path, snapshot):
                return False
            sources += 1
        elif kind == "probe":
            if not _probe_matches(path, snapshot):
                return False
        elif kind == "static":
            if not _static_matches(path, snapshot):
                return False
        else:
            return False
    return sources > 0


def lookup(cache_root: str, context: str) -> str:
    try:
        root = _cache_dir(cache_root)
        if root == "":
            return ""
        _load_memo(root)
        index = root + "/" + fnv(context) + ".manifest"
        fields = _document(index, MAGIC)
        if len(fields) < 2 or fields[0] != context or not _hex(fields[1]) or not _valid_records(fields):
            return ""
        # A manifest can name only a content-addressed basename in this directory.
        executable = root + "/" + fields[1] + ".exe"
        if not _regular(executable) or os.path.getsize(executable) == 0 or _file_hash(executable) != fields[1]:
            return ""
        return executable if _sh("[ -x " + _q(executable) + " ]") else ""
    except (OSError, ValueError):
        return ""


def _records(context: str, digest: str) -> list[str]:
    fields = [context, digest]
    for path in sorted(SOURCES):
        fields.extend(["source", path, SOURCES[path]])
    for path in sorted(PROBES):
        fields.extend(["probe", path, PROBES[path]])
    for path in sorted(STATICS):
        fields.extend(["static", path, STATICS[path]])
    return fields


def publish(cache_root: str, context: str, executable: str) -> str:
    stage = ""
    try:
        if not VALID[0] or len(SOURCES) == 0 or not _regular(executable):
            return ""
        root = _cache_dir(cache_root)
        if root == "" or not _valid_records(_records(context, "")):
            return ""
        # mkdtemp supplies a random name even across PID namespaces. The actual
        # staging directory is on the cache's filesystem, for atomic renames.
        token = tempfile.mkdtemp()
        os.rmdir(token)
        stage = root + "/stage-" + token[token.rfind("/") + 1:]
        os.mkdir(stage, 0o700)
        part = stage + "/program"
        if not _sh("cp -- " + _q(executable) + " " + _q(part) + " && chmod 700 -- " + _q(part)
                   + " && [ -x " + _q(part) + " ]"):
            return ""
        digest = _file_hash(part)
        if digest == "" or os.path.getsize(part) == 0:
            return ""
        fields = _records(context, digest)
        payload = _pack(fields)
        text = MAGIC + fnv(payload) + "\n" + payload
        if len(text) > MAX_MANIFEST or len(fields) > MAX_FIELDS:
            return ""
        index = stage + "/manifest"
        f = open(index, "w", encoding="utf-8", newline="")
        try:
            f.write(text)
        finally:
            f.close()
        # Recheck after copying the binary and writing the manifest, so a change
        # during a long compile or publication never publishes the old snapshot.
        if not VALID[0] or not _valid_records(fields):
            return ""
        target = root + "/" + digest + ".exe"
        os.replace(part, target)
        os.replace(index, root + "/" + fnv(context) + ".manifest")
        _save_memo(root, stage)
        return target
    except (OSError, ValueError):
        return ""
    finally:
        if stage != "":
            for name in ["program", "manifest", "memo"]:
                try:
                    os.unlink(stage + "/" + name)
                except OSError:
                    pass
            try:
                os.rmdir(stage)
            except OSError:
                pass
