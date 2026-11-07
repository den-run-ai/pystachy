"""Bounded search-layout snapshots for the standard Linux native toolchain.

Consumed file contents are recorded separately by program_cache. This module
records search candidates as well: adding a header/GCC installation/library, or
making an existing candidate usable, must invalidate an executable cache hit.
Only a miss invokes clang to discover its search paths. Hits replay snapshots.
"""
from __future__ import annotations
import os
import tempfile


MAX_ENTRIES: int = 20000
MAX_OUTPUT: int = 1024 * 1024
GENTOO_CONFIG: str = "/etc/env.d/gcc"
# Clang's Linux distro detector changes linker defaults and the interpreter
# path. Missing files matter too: adding an earlier release file can win.
SYSTEM_INPUTS: list[str] = [
    "/etc/ld.so.cache", "/etc/ld.so.preload", "/etc/os-release",
    "/usr/lib/os-release", "/etc/lsb-release", "/etc/redhat-release",
    "/etc/debian_version", "/etc/SuSE-release", "/etc/gentoo-release",
]


def _pack(fields: list[str]) -> str:
    return "".join([str(len(s)) + ":" + s for s in fields])


def _quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def snapshot(path: str) -> str:
    """Capture candidate metadata; canonical traversal avoids per-file realpath."""
    try:
        # collect records canonical tree entries and each symlink spelling. Do
        # not resolve every regular file's ancestors on every hit: that would
        # multiply the directory probes by the depth of every header path.
        real = os.path.realpath(path) if os.path.islink(path) else ""
        # The outer manifest length-delimits this opaque value. A path cannot
        # contain NUL, so direct separators avoid per-field length formatting
        # and temporary lists on the thousands of candidate checks per hit.
        return f"stat1\0{real}\0{os.path.getsize(path)}\0{os.path.getmtime(path)}\0{os.path.getctime(path)}"
    except OSError:
        return "missing1\0" + os.path.realpath(path) if not os.path.exists(path) else ""
    except ValueError:
        return ""


def valid(records: dict[str, str]) -> bool:
    return len(records) > 0 and all(value != "" and snapshot(path) == value
                                   for path, value in records.items())


def token(records: dict[str, str]) -> str:
    """Stable input for the program and runtime object cache identities."""
    fields: list[str] = []
    for path in sorted(records):
        fields.extend([path, records[path]])
    return _pack(fields)


def _absolute(path: str) -> bool:
    return path.startswith("/") and "\0" not in path and "\n" not in path and "\r" not in path


def _parent(path: str) -> str:
    # Compiler modules stay within the native subset, which has no dirname.
    slash = path.rfind("/")
    return path[:slash] if slash > 0 else "/"


def include_roots(text: str) -> list[str]:
    """Parse both existing includes and clang's failed include-directory probes."""
    roots: dict[str, bool] = {}
    active = False
    complete = False
    for line in text.split("\n"):
        if line in ['#include "..." search starts here:', '#include <...> search starts here:']:
            active = True
        elif line == "End of search list.":
            active = False
            complete = True
        elif active:
            path = line.strip()
            if not _absolute(path):
                return []
            roots[path] = True
        elif line.startswith('ignoring nonexistent directory "') and line.endswith('"'):
            path = line[len('ignoring nonexistent directory "'):-1]
            if not _absolute(path):
                return []
            roots[path] = True
    return sorted(roots) if complete else []


def library_roots(text: str) -> list[str]:
    roots: dict[str, bool] = {}
    libraries = False
    for line in text.split("\n"):
        if line.startswith("libraries: ="):
            # The supported default tier uses absolute LLVM tool paths,
            # clang's integrated assembler and an explicit /usr/bin/ld.
            # Unrelated executables in a programs: directory are not inputs.
            libraries = True
            for path in line.split("=", 1)[1].split(":"):
                if not _absolute(path):
                    return []
                roots[path] = True
    return sorted(roots) if libraries else []


def config_roots(text: str, name: str) -> list[str]:
    # An intentionally missing --config file makes clang report its actual
    # compiled user/system/executable search roots, including absent paths.
    # Guessing /etc/clang or ~/.config/clang would miss custom LLVM builds.
    if "configuration file '" + name + "' cannot be found" not in text:
        return []
    prefix = "clang: note: was searched for in the directory: "
    roots: dict[str, bool] = {}
    for line in text.split("\n"):
        if line.startswith(prefix):
            path = line[len(prefix):]
            if not _absolute(path):
                return []
            roots[path] = True
    return sorted(roots)


def linker_roots(text: str) -> list[str]:
    roots: dict[str, bool] = {}
    prefix = 'SEARCH_DIR("'
    for line in text.split("\n"):
        for part in line.split(prefix)[1:]:
            end = part.find('")')
            if end < 0:
                return []
            path = part[:end]
            if path.startswith("="):
                path = path[1:]
            if not _absolute(path):
                return []
            roots[path] = True
    return sorted(roots)


def loader_roots(text: str) -> list[str]:
    # glibc's loader reports every RUNPATH/default/hardware search candidate,
    # including missing ones. ldd observes this without running program code.
    roots: dict[str, bool] = {}
    # glibc ldd can exit successfully even when a required library is missing.
    if "=> not found" in text:
        return []
    for line in text.split("\n"):
        start = line.find("search path=")
        if start >= 0:
            value = line[start + len("search path="):]
            end = value.find("\t(")
            if end < 0:
                return []
            for path in value[:end].split(":"):
                if not _absolute(path):
                    return []
                roots[path] = True
    return sorted(roots)


def gcc_roots(llvm: str, verbose: str) -> list[str]:
    # Standard clang GCC discovery uses the installation prefix, /usr and
    # /opt/rh. Include missing alternatives, not merely the selected version.
    # A custom default sysroot adds earlier GCC prefixes which this standard
    # Linux discovery contract does not infer from a selected installation.
    if " -isysroot " in verbose or ' "-isysroot" ' in verbose:
        return []
    roots: dict[str, bool] = {"/opt/rh": True}
    prefixes = ["/usr", _parent(llvm), _parent(os.path.realpath(llvm))]
    for line in verbose.split("\n"):
        prefix = "Found candidate GCC installation: "
        if line.startswith(prefix):
            path = line[len(prefix):]
            if not _absolute(path):
                return []
            # Capture siblings of the target/version that clang discovered.
            root = _parent(_parent(path))
            roots[root] = True
            if root.endswith("/gcc") or root.endswith("/gcc-cross"):
                # A configured GCC prefix may first provide lib64/gcc, then
                # gain a preferred installation in its sibling lib/gcc.
                prefixes.append(_parent(_parent(root)))
    for prefix in prefixes:
        for lib in ["lib", "lib32", "lib64"]:
            for gcc in ["gcc", "gcc-cross"]:
                roots[prefix + "/" + lib + "/" + gcc] = True
    return sorted(roots)


def collect(roots: list[str], shallow: list[str], configs: list[str]) -> dict[str, str]:
    """Capture recursive include/GCC trees and shallow native search directories.

    File metadata is necessary too: chmod or replacing an incompatible library
    in place may make an ignored search candidate usable without changing its
    parent directory. Content hashes remain limited to actually consumed files.
    Library directories are searched directly, so unrelated language packages
    below /usr/lib do not belong in the cache's dependency tree.
    """
    records: dict[str, str] = {}
    scanned: dict[str, bool] = {}
    pending = roots[:]
    try:
        for root in roots + shallow + configs:
            if not _absolute(root):
                return {}
            # An alias in an ancestor of a discovered root can be retargeted
            # without modifying the old canonical tree.
            parent = root
            while parent != "/":
                if os.path.islink(parent):
                    records[parent] = snapshot(parent)
                parent = _parent(parent)
        while len(pending) > 0:
            path = pending.pop()
            stamp = snapshot(path)
            if stamp == "":
                return {}
            records[path] = stamp
            if len(records) > MAX_ENTRIES:
                return {}
            if not os.path.isdir(path):
                continue
            real = os.path.realpath(path)
            if real in scanned:
                continue
            scanned[real] = True
            before = snapshot(real)
            records[real] = before
            for name in os.listdir(real):
                child = real + "/" + name
                child_stamp = snapshot(child)
                if child_stamp == "":
                    return {}
                records[child] = child_stamp
                if len(records) > MAX_ENTRIES:
                    return {}
                if os.path.isdir(child):
                    pending.append(child)
            if snapshot(real) != before:
                return {}
        for path in shallow:
            records[path] = snapshot(path)
            if os.path.isdir(path):
                real = os.path.realpath(path)
                before = snapshot(real)
                records[real] = before
                for name in os.listdir(real):
                    child = real + "/" + name
                    records[child] = snapshot(child)
                    if len(records) > MAX_ENTRIES:
                        return {}
                if snapshot(real) != before:
                    return {}
        for path in configs:
            records[path] = snapshot(path)
            if os.path.isdir(path):
                before = records[path]
                for name in os.listdir(path):
                    if name.endswith(".cfg"):
                        return {}
                if snapshot(path) != before:
                    return {}
        return records if len(records) <= MAX_ENTRIES and valid(records) else {}
    except (OSError, ValueError):
        return {}


def _read(path: str) -> str:
    if os.path.getsize(path) > MAX_OUTPUT:
        return ""
    f = open(path, "r", encoding="latin-1", newline="")
    text = f.read()
    f.close()
    return text


def capture(llvm: str) -> dict[str, str]:
    """Discover standard clang search roots; return no records when uncertain."""
    # Gentoo gcc-config can point to arbitrary extra installations. Keep this
    # configuration outside the default contract, and record its absence below.
    if os.path.exists(GENTOO_CONFIG):
        return {}
    tmp = tempfile.mkdtemp()
    verbose = tmp + "/verbose"
    search = tmp + "/search"
    config = tmp + "/config"
    linker = tmp + "/linker"
    loader = tmp + "/loader"
    name = "pystachy-" + tmp[tmp.rfind("/") + 1:] + ".cfg"
    compiler = _quote(llvm + "/clang")
    records: dict[str, str] = {}
    try:
        first = os.system(compiler + " -v -E -x c /dev/null > /dev/null 2> " + _quote(verbose))
        second = os.system(compiler + " -print-search-dirs > " + _quote(search) + " 2> /dev/null")
        third = os.system(compiler + " --config=" + _quote(name)
                          + " -### -x c /dev/null > /dev/null 2> " + _quote(config))
        fourth = os.system("/usr/bin/ld --verbose > " + _quote(linker) + " 2> /dev/null")
        tools = [os.path.realpath("/proc/self/exe")] + [llvm + "/" + name for name in ["clang", "opt", "llvm-as", "llvm-link", "lli"]]
        declared = os.getenv("PYSTACHY_PROGRAM_CACHE_INPUTS", "")
        tools += [p for p in declared.split(":") if p != ""]
        fifth = os.system("LD_DEBUG=libs /usr/bin/ldd " + " ".join([_quote(p) for p in tools])
                          + " > " + _quote(loader) + " 2>&1")
        if first == 0 and second == 0 and third != 0 and fourth == 0 and (fifth == 0 or declared != ""):
            details = _read(verbose)
            headers = include_roots(details)
            libraries = library_roots(_read(search))
            configs = config_roots(_read(config), name)
            linker_dirs = linker_roots(_read(linker))
            loader_dirs = loader_roots(_read(loader))
            gcc = gcc_roots(llvm, details)
            if len(headers) > 0 and len(libraries) > 0 and len(configs) > 0 and len(gcc) > 0 and len(linker_dirs) > 0 and len(loader_dirs) > 0:
                libraries += linker_dirs + loader_dirs
                # glibc searches these subtrees of a library directory. Their
                # missing roots also record future hardware-directory additions.
                hardware: list[str] = []
                for path in libraries:
                    hardware += [path + "/glibc-hwcaps", path + "/tls"]
                records = collect(headers + gcc + hardware,
                                  libraries + SYSTEM_INPUTS + [GENTOO_CONFIG], configs)
                if os.path.exists(GENTOO_CONFIG):
                    records = {}
    except (OSError, ValueError):
        records = {}
    finally:
        for path in [verbose, search, config, linker, loader]:
            try:
                os.unlink(path)
            except OSError:
                pass
        os.rmdir(tmp)
    return records
