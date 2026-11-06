"""Complete-program cache; the driver supplies the compilation identity.

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
from src.pystachy_compiler import cache_toolchain


MAGIC = "pystachy-program-cache-2\n"
MEMO_MAGIC = "pystachy-static-hashes-1\n"
MAX_MANIFEST = 8 * 1024 * 1024
MAX_FIELDS = 65536
MAX_BINARY = 512 * 1024 * 1024
MAX_CACHE_BYTES = 256 * 1024 * 1024
MAX_CACHE_ENTRIES = 256
ACTIVE: list[bool] = [False]
VALID: list[bool] = [True]
SOURCES: dict[str, str] = {}
PROBES: dict[str, str] = {}
STATICS: dict[str, str] = {}
LAYOUTS: dict[str, str] = {}
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


def _sha256(path: str) -> str:
    # Hash large toolchain inputs in coreutils' byte-oriented implementation.
    # The compiler's character loop is useful for small files but disproportionately
    # expensive for LLVM libraries. A private output file keeps this self-hostable
    # without a subprocess API or runtime ABI addition.
    stage = ""
    try:
        if "\0" in path or not os.path.isfile(path) or os.path.getsize(path) > MAX_BINARY:
            return ""
        stage = tempfile.mkdtemp()
        output = stage + "/digest"
        if not _sh("/usr/bin/sha256sum < " + _q(path) + " > " + _q(output)):
            return ""
        read = _read(output, 68, "utf-8")
        text = read[1]
        # Reading through stdin avoids filename escaping in sha256sum's output.
        digest = "sha256:" + text[:64]
        if read[0] and len(text) == 68 and text[64:] == "  -\n" and _static_digest(digest):
            return digest
        return ""
    except (OSError, ValueError):
        return ""
    finally:
        if stage != "":
            try:
                os.unlink(stage + "/digest")
            except OSError:
                pass
            try:
                os.rmdir(stage)
            except OSError:
                pass


def _static_hash(path: str) -> str:
    try:
        if os.path.getsize(path) >= 1024 * 1024:
            digest = _sha256(path)
            if digest != "":
                return digest
        # A missing or unusable coreutils helper loses speed, never validation.
        return _file_hash(path)
    except (OSError, ValueError):
        return ""


def start() -> None:
    SOURCES.clear()
    PROBES.clear()
    STATICS.clear()
    LAYOUTS.clear()
    VALID[0] = True
    ACTIVE[0] = True


def stop() -> None:
    ACTIVE[0] = False


def track_layout(records: dict[str, str]) -> None:
    if ACTIVE[0]:
        if len(records) == 0:
            VALID[0] = False
        for path in records:
            _record(LAYOUTS, path, records[path])


def runtime_key() -> str:
    # Runtime objects must reflect the same headers and search choices as the
    # complete program. A newly captured manifest must not bless an older .o.
    fields: list[str] = []
    for path in sorted(STATICS):
        parts = _unpack(STATICS[path])
        if len(parts) == 4:
            fields.extend([path, parts[0], parts[2]])
    for path in sorted(LAYOUTS):
        fields.extend([path, LAYOUTS[path]])
    return fnv(_pack(fields))


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
    if len(fields) != 4 or fields[3] not in ["0", "1"] or not _static_digest(fields[2]):
        return False
    if os.path.realpath(path) != fields[0] or _stat3(path) != fields[1] or fields[1] == "":
        return False
    # A timestamp may be trusted only if it was settled when the bytes were read.
    # A racy capture remains content-checked even after its timestamp grows older.
    if fields[3] == "1":
        return True
    digest = _sha256(path) if fields[2].startswith("sha256:") else _file_hash(path)
    return digest == fields[2] and _stat3(path) == fields[1]


def track_static(path: str) -> None:
    if not ACTIVE[0]:
        return
    try:
        real = os.path.realpath(path)
        st = _stat3(path)
        snapshot = STATIC_MEMO.get(real, "")
        if snapshot == "" or not _static_matches(path, snapshot):
            digest = _static_hash(path)
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
    # Linux cache: GNU stat supplies the mode; the shell checks ownership.
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
        root = base + "/program-v2"
        if not os.path.lexists(root):
            try:
                os.mkdir(root, 0o700)
            except OSError:
                pass  # another writer may have created it
        return root if _safe_dir(root, True) else ""
    except (OSError, ValueError):
        return ""


# Lock files are permanent: unlinking one while another process waits on it
# could create two independently locked inodes for the same bucket.
def lock_path(cache_root: str, context: str) -> str:
    root = _cache_dir(cache_root)
    if root == "":
        return ""
    return _bucket_lock(root, fnv(context)[:2])


def _bucket_lock(root: str, bucket: str) -> str:
    path = root + "/lock-" + bucket
    q = _q(path)
    try:
        if not os.path.lexists(path):
            _sh("(umask 077; set -C; : > " + q + ")")
        if _regular(path) and _sh("[ -O " + q + " ]"):
            return path
    except (OSError, ValueError):
        pass
    return ""


def lock_held(cache_root: str, context: str) -> bool:
    # The launch layer proves kernel lock ownership before using this inherited
    # descriptor. No successful-launch marker enters the program environment.
    root = _cache_dir(cache_root)
    return root != "" and _holds_bucket(root, fnv(context)[:2])


def _holds_bucket(root: str, bucket: str) -> bool:
    try:
        return os.path.samefile(root + "/lock-" + bucket, "/proc/self/fd/9")
    except (OSError, ValueError):
        return False


def _hex(s: str) -> bool:
    if len(s) != 16:
        return False
    for c in s:
        if c not in "0123456789abcdef":
            return False
    return True


def _static_digest(s: str) -> bool:
    if _hex(s):
        return True
    if len(s) != 71 or not s.startswith("sha256:"):
        return False
    for c in s[7:]:
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
                and _static_digest(parts[2]) and parts[3] == "1"):
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
        # Accepted kinds contain no colon, so this remains unambiguous without
        # allocating and length-encoding a pair for every search candidate.
        key = kind + ":" + path
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
        elif kind == "layout":
            if cache_toolchain.snapshot(path) != snapshot or snapshot == "":
                return False
        else:
            return False
    return sources > 0


def _entry_key(name: str) -> str:
    if name.endswith(".manifest") and _hex(name[:-9]):
        return name[:-9]
    if (len(name) == 37 and name[16] == "-" and name.endswith(".exe")
            and _hex(name[:16]) and _hex(name[17:33])):
        return name[:16]
    return ""


def _stage_key(name: str) -> str:
    if name.startswith("stage-") and len(name) > 23 and name[22] == "-" and _hex(name[6:22]):
        return name[6:22]
    return ""


def _bucket_action(root: str, bucket: str, held: str, command: str) -> bool:
    if bucket == held:
        return _sh(command)
    lock = _bucket_lock(root, bucket)
    if lock == "":
        return False
    # The child has its own descriptor, while FD9 belongs to the running
    # compiler. Nonblocking acquisition avoids a lock-order cycle between two
    # different compilers pruning each other's entries.
    return _sh("(exec 7> " + _q(lock) + " && /usr/bin/flock -n 7 && " + command + ")")


def _stage_command(path: str) -> str:
    # Never recurse into a stage or follow a symlink. Only these filenames are
    # created by this module; an unexpected file leaves the directory intact.
    q = _q(path)
    files = " ".join([_q(path + "/" + n) for n in ["program", "manifest", "memo"]])
    return "[ ! -L " + q + " ] && [ -d " + q + " ] && rm -f -- " + files + " && rmdir -- " + q


def _clean_stages(root: str, held: str, keep: str, all_buckets: bool) -> None:
    for name in os.listdir(root):
        key = _stage_key(name)
        if key != "" and root + "/" + name != keep and (all_buckets or key[:2] == held):
            _bucket_action(root, key[:2], held, _stage_command(root + "/" + name))


def cleanup(cache_root: str, context: str) -> None:
    # Reclaim a killed predecessor as soon as its bucket is acquired. There is
    # no timeout or PID-reuse assumption: flock says whether a writer is alive.
    try:
        root = _cache_dir(cache_root)
        if root != "" and _holds_bucket(root, fnv(context)[:2]):
            _clean_stages(root, fnv(context)[:2], "", False)
    except (OSError, ValueError):
        pass


def _clean_executables(root: str, key: str, keep: str) -> None:
    for name in os.listdir(root):
        if _entry_key(name) == key and name.endswith(".exe") and root + "/" + name != keep:
            try:
                os.unlink(root + "/" + name)
            except OSError:
                pass


def _prune(root: str, key: str, held: str, stage: str) -> bool:
    if held != "":
        _clean_stages(root, held, stage, True)
    sizes: dict[str, int] = {}
    ages: dict[str, float] = {}
    total = 0
    for name in os.listdir(root):
        entry = _entry_key(name)
        path = root + "/" + name
        if entry != "" and not os.path.isdir(path):
            # A corrupt symlink can be unlinked, but never follow it for size
            # accounting or derive a deletion target from its contents. Another
            # pruning writer may have already removed a file in this census.
            try:
                size = os.path.getsize(path) if _regular(path) else 0
                age = os.path.getmtime(path) if name.endswith(".manifest") and _regular(path) else 0.0
            except OSError:
                continue
            total += size
            sizes[entry] = sizes.get(entry, 0) + size
            if name.endswith(".manifest"):
                ages[entry] = age
    count = len(sizes)
    order = sorted([(ages.get(entry, 0.0), entry) for entry in sizes])
    for pair in order:
        entry = pair[1]
        if count <= MAX_CACHE_ENTRIES and total <= MAX_CACHE_BYTES:
            return True
        if entry != key:
            # The bucket lock protects lookup through opening the executable,
            # and publication. Remove the manifest before its binary siblings.
            # Enumerate the exact basename pattern while the lock is held:
            # another writer may have replaced this entry since our census.
            pattern = "[0-9a-f]" * 16
            cmd = "rm -f -- " + _q(root + "/" + entry + ".manifest")
            cmd += " " + _q(root + "/" + entry + "-") + pattern + ".exe"
            if _bucket_action(root, entry[:2], held, cmd):
                total -= sizes[entry]
                count -= 1
    return count <= MAX_CACHE_ENTRIES and total <= MAX_CACHE_BYTES


def lookup(cache_root: str, context: str) -> str:
    root = ""
    hit = ""
    try:
        root = _cache_dir(cache_root)
        if root == "":
            return ""
        key = fnv(context)
        held = _holds_bucket(root, key[:2])
        if held:
            _clean_stages(root, key[:2], "", False)
        index = root + "/" + key + ".manifest"
        fields = _document(index, MAGIC)
        executable = ""
        if len(fields) >= 2 and fields[0] == context and _hex(fields[1]):
            executable = root + "/" + key + "-" + fields[1] + ".exe"
        if held:
            _clean_executables(root, key, executable)
        if executable == "" or not _valid_records(fields):
            return ""
        # Every executable belongs to one context; an eviction never removes
        # a blob still referenced by another context's manifest.
        if not _regular(executable) or os.path.getsize(executable) == 0 or _file_hash(executable) != fields[1]:
            return ""
        if not _sh("[ -x " + _q(executable) + " ]"):
            return ""
        # LRU metadata is optional. A read-only cache can still serve a hit.
        _sh("touch -- " + _q(index))
        hit = executable
        return hit
    except (OSError, ValueError):
        return ""
    finally:
        # Hits validate their recorded hashes directly. Only a miss needs the
        # separate memo used to avoid rehashing toolchain files during capture.
        if root != "" and hit == "":
            _load_memo(root)


def _records(context: str, digest: str) -> list[str]:
    fields = [context, digest]
    for path in sorted(SOURCES):
        fields.extend(["source", path, SOURCES[path]])
    for path in sorted(PROBES):
        fields.extend(["probe", path, PROBES[path]])
    for path in sorted(STATICS):
        fields.extend(["static", path, STATICS[path]])
    for path in sorted(LAYOUTS):
        fields.extend(["layout", path, LAYOUTS[path]])
    return fields


def publish(cache_root: str, context: str, executable: str) -> str:
    stage = ""
    root = ""
    key = ""
    target = ""
    committed = False
    try:
        if not VALID[0] or len(SOURCES) == 0 or not _regular(executable):
            return ""
        root = _cache_dir(cache_root)
        if root == "" or not _valid_records(_records(context, "")):
            return ""
        key = fnv(context)
        held = key[:2] if _holds_bucket(root, key[:2]) else ""
        if os.path.getsize(executable) > MAX_CACHE_BYTES:
            return ""
        # mkdtemp supplies a random name even across PID namespaces. The actual
        # staging directory is on the cache's filesystem, for atomic renames.
        token = tempfile.mkdtemp()
        os.rmdir(token)
        stage = root + "/stage-" + key + "-" + token[token.rfind("/") + 1:]
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
        target = root + "/" + key + "-" + digest + ".exe"
        os.replace(part, target)
        os.replace(index, root + "/" + key + ".manifest")
        committed = True
        if held != "":
            _clean_executables(root, key, target)
        # Prune after publication: the last of concurrent writers observes all
        # earlier commits. If active entries fill the budget, decline this new
        # entry instead of deleting an executable another launcher is opening.
        if not _prune(root, key, held, stage):
            os.unlink(root + "/" + key + ".manifest")
            _clean_executables(root, key, "")
            return ""
        _save_memo(root, stage)
        return target
    except (OSError, ValueError):
        # A failed census or cleanup must not leave a new over-budget entry.
        # The previous manifest remains intact until committed becomes true.
        if committed:
            try:
                os.unlink(root + "/" + key + ".manifest")
            except OSError:
                pass
            try:
                _clean_executables(root, key, "")
            except OSError:
                pass
        elif target != "":
            # The executable rename may have succeeded before the manifest
            # failed. Reclaim that orphan immediately, but preserve the old
            # entry when its complete manifest names this same binary digest.
            try:
                previous = _document(root + "/" + key + ".manifest", MAGIC)
                referenced = ""
                if len(previous) >= 2 and _hex(previous[1]):
                    referenced = root + "/" + key + "-" + previous[1] + ".exe"
                if target != referenced:
                    os.unlink(target)
            except (OSError, ValueError):
                pass
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
