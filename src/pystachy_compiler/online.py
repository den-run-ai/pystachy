"""Fail-closed packaging for the experimental Linux AOT online tier.

An online image contains ordinary compiler output and immutable literals. It
imports the running program's globals and runtime; it never initializes either.
"""
from __future__ import annotations
import os
from src.pystachy_compiler.diagnostics import RAW, fail
from src.pystachy_compiler.utils import llstr, lt


def online_hash(s: str) -> str:
    # Same byte hash as the driver's runtime cache, with bounded integer products.
    hi = 0xCBF29CE4
    lo = 0x84222325
    for c in s:
        lo ^= ord(c)
        m = lo * 0x1B3
        hi = (hi * 0x1B3 + (lo << 8) + (m >> 32)) & 0xFFFFFFFF
        lo = m & 0xFFFFFFFF
    return f"{hi:08x}{lo:08x}"


def online_file(path: str) -> str:
    try:
        f = open(path, "r", encoding=RAW, newline="")
        data = f.read()
        f.close()
        return online_hash(data)
    except OSError:
        return "missing"


def online_identity(sources: dict[str, str], home: str, components: list[str]) -> str:
    rows = ["pystachy-online-v1", "abi\tlinux-native-64\ti64(ptr)\t1"]
    parsed: dict[str, str] = {}
    for path in sources:
        parsed[os.path.realpath(path)] = online_hash(sources[path])
    for path in sorted(parsed):
        rows.append("source\t" + path + "\t" + parsed[path])
    for path in components + ["runtime.c", "runtime.py"]:
        rows.append("compiler\t" + path + "\t" + online_file(home + "/" + path))
    compiler = os.getenv("PYSTACHY_ONLINE_COMPILER", "")
    rows.append("binary\t" + os.path.realpath(compiler) + "\t" + online_file(compiler))
    for key in ["PYSTACHY_CLOSED_UNIONS", "PYSTACHY_REFERENCE_UNIONS", "PYSTACHY_OPT", "PYSTACHY_FLOW_LOCALS", "PYSTACHY_CFLAGS", "PYSTACHY_ONLINE_INLINE_RUNTIME"]:
        rows.append("option\t" + key + "\t" + os.getenv(key, ""))
    return "\n".join(rows) + "\n"


def online_abi(self) -> str:
    rows: list[str] = []
    for g in sorted(self.globs):
        rows.append("global\t" + g)
    for name in sorted(self.classes):
        ci = self.classes[name]
        if name in self.tmpl:
            continue
        fields = ",".join([x + ":" + ci.ftypes[x] + ":" + lt(ci.ftypes[x]) for x in ci.fields])
        flags = ",".join([x + ":" + str(ci.fflag[x]) for x in sorted(ci.fflag)])
        rows.append("class\t" + name + "\t" + ci.base + "\t" + str(ci.tag) + "\t" + str(ci.nflag) + "\t" + fields + "\t" + flags)
    for name in sorted(self.utags):
        rows.append("union\t" + name + "\t" + str(self.utags[name]))
    for name in sorted(self.ocls):
        rows.append("object\t" + name + "\t" + str(self.ocls[name]))
    for site in sorted(self.online_signatures):
        rows.append("site\t" + site + "\t" + self.online_signatures[site])
    for key in sorted(self.adapters):
        if key.startswith("fn[f:"):
            rows.append("adapter\t" + key + "\t" + self.adapters[key])
    for c in self.consts:
        info = online_constant(c)
        rows.append("literal\t" + info[0] + "\t" + info[1] + "\t" + online_hash(c))
    return "\n".join(rows) + "\n"


def online_constant(c: str) -> tuple[str, str]:
    at = c.find(" = private ")
    tail = c[at + 11 :]
    prefix = "unnamed_addr global " if tail.startswith("unnamed_addr global ") else "constant "
    if at < 0 or not tail.startswith(prefix) or not tail[len(prefix):].startswith("{"):
        fail("online compilation encountered an unsupported literal", 0)
    tail = tail[len(prefix):]
    end = tail.find("}")
    if end < 0:
        fail("online compilation encountered a malformed literal", 0)
    return (c[:at], tail[:end + 1])


def online_capture(self) -> None:
    if self.rtmode or not (self.online_host or self.online_child):
        return
    if len(self.externs) > 0:
        fail("online compilation does not support foreign declarations", 0)
    self.online_baseline = online_abi(self)
    manifest = self.online_identity + self.online_baseline
    if len(manifest) > 262144:
        fail("online compilation manifest exceeds 262144 bytes", 0)
    if self.online_child:
        try:
            f = open(self.online_expect, "r", encoding=RAW, newline="")
            expected = f.read(262145)
            f.close()
        except OSError:
            fail("online compilation cannot read the host ABI manifest", 0)
            return
        if manifest != expected:
            fail("online compilation source or baseline ABI differs from the running host", 0)


def online_validate(self) -> None:
    if not self.online_child or self.rtmode:
        return
    if self.online_entry != "@pystachy_online_entry":
        fail("online compilation did not produce an eligible entry", 0)
    before = self.online_baseline.splitlines()
    after = online_abi(self).splitlines()
    # All host identities must still exist exactly. New globals have no original
    # storage or root; new O descriptors have no host runtime dispatch entry.
    for row in before:
        if row not in after:
            fail("online compilation changed a shared layout, tag or signature", 0)
    for row in after:
        if row not in before:
            if row.startswith("literal\t@s."):
                continue  # a new private literal in code only the clone needs
            if not row.startswith("class\t"):
                fail("online compilation introduced shared state or a runtime descriptor", 0)
            name = row.split("\t")[1]
            if self.classes[name].origin == "":
                fail("online compilation introduced a non-template class", 0)


def online_globals(self) -> list[str]:
    if self.rtmode or not (self.online_host or self.online_child):
        return self.globs
    rows: list[str] = []
    for g in self.globs:
        if " = internal global " not in g:
            fail("online compilation encountered unsupported mutable storage", 0)
        if self.online_child:
            rows.append(g.replace(" = internal global ", " = external global ").replace(" zeroinitializer", ""))
        else:
            rows.append(g.replace(" = internal global ", " = global "))
    return rows


def online_constants(self) -> list[str]:
    if self.rtmode or not (self.online_host or self.online_child):
        return self.consts
    shared: dict[str, str] = {}
    for row in self.online_baseline.splitlines():
        if row.startswith("literal\t"):
            parts = row.split("\t")
            shared[parts[1]] = parts[2]
    rows: list[str] = []
    for c in self.consts:
        info = online_constant(c)
        name = info[0]
        if name not in shared:
            rows.append(c)
        elif self.online_child:
            kind = "global " if name.startswith("@s.") else "constant "
            rows.append(name + " = external " + kind + shared[name])
        else:
            # Hash-cache bytes are writable; string addresses are now observable
            # across images, so do not mark these shared literals unnamed_addr.
            rows.append(c.replace(" = private unnamed_addr global ", " = global ").replace(" = private constant ", " = constant "))
    return rows


def online_metadata(self) -> list[str]:
    rows: list[str] = []
    for name in ["abi", "selection"]:
        value = self.online_identity + self.online_baseline if name == "abi" else self.online_site + "\t" + self.online_member
        symbol = "@pystachy.online." + name
        rows.append(f'{symbol} = private constant [{len(value) + 1} x i8] c"{llstr(value)}\\00"')
        rows.append(f"define ptr @pystachy_online_{name}() {{")
        rows.append(f"  ret ptr {symbol}")
        rows.append("}")
    return rows


def online_image(ir: str) -> str:
    # Keep only the explicit entry public. LLVM's globaldce removes module init,
    # baseline bodies and duplicate object dispatch before the shared link.
    rows: list[str] = []
    for row in ir.splitlines():
        public = " @pystachy_online_entry(" in row or " @pystachy_online_abi(" in row or " @pystachy_online_selection(" in row
        if row.startswith("define ") and not row.startswith("define internal ") and not public:
            row = "define internal " + row[7:]
        rows.append(row)
    return "\n".join(rows) + "\n"


def online_runtime_symbols(row: str) -> list[str]:
    # opt's printed IR uses unquoted names here. Quoted identifiers and inline
    # assembly are deliberately outside this importer's grammar. Ignore strings
    # and comments, which may contain an @ that does not name an LLVM value.
    names: list[str] = []
    i = 0
    while i < len(row):
        c = row[i]
        if c == ";":
            break
        if c == '"':
            i += 1
            while i < len(row) and row[i] != '"':
                i += 2 if row[i] == "\\" else 1
        elif c == "@":
            j = i + 1
            while j < len(row) and row[j] in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.$_":
                j += 1
            if j == i + 1:
                return [""]
            names.append(row[i + 1 : j])
            i = j - 1
        i += 1
    return names


def online_runtime_declaration(header: str) -> str:
    # Keep the exact ABI and parameter attributes, but no body-only attributes,
    # personality or metadata. An imported symbol must not remain dso_local.
    start = header.find("@")
    end = header.find("(", start)
    depth = 1
    end += 1
    while end < len(header) and depth > 0:
        if header[end] == "(":
            depth += 1
        elif header[end] == ")":
            depth -= 1
        end += 1
    if start < 0 or depth != 0:
        fail("online runtime import encountered an unsupported function signature", 0)
    prefix = header[7 : start]
    for word in ["dso_local ", "dso_preemptable ", "available_externally ", "linkonce_odr ", "weak_odr ", "linkonce ", "weak ", "external "]:
        prefix = prefix.replace(word, "")
    return "declare " + prefix + header[start:end]


def online_runtime_import(ir: str) -> str:
    # Import code, never storage. Public bodies with no global-data references
    # may inline, while their residual calls still resolve to the running host.
    # A private helper must have a safe body too and may only be called directly:
    # copying its address could change an observable callback identity. No data
    # global is copied, even an immutable constant or a literal's hash cache.
    bodies: dict[str, list[str]] = {}
    public: dict[str, bool] = {}
    declared: dict[str, bool] = {}
    refs: dict[str, list[str]] = {}
    safe: dict[str, bool] = {}
    other: list[str] = []
    name = ""
    for row in ir.splitlines():
        if row.startswith("define "):
            symbols = online_runtime_symbols(row)
            if name != "" or len(symbols) == 0 or symbols[0] == "" or not row.endswith("{"):
                fail("online runtime import encountered an unsupported definition", 0)
            name = symbols[0]
            bodies[name] = [row]
            refs[name] = symbols[1:]
            prefix = row[: row.find("@")]
            public[name] = " internal " not in prefix and " private " not in prefix
            safe[name] = not any(word in prefix for word in [" weak ", " weak_odr ", " linkonce ", " linkonce_odr ", " available_externally "])
        elif name != "":
            bodies[name].append(row)
            refs[name] = refs[name] + online_runtime_symbols(row)
            if " asm " in row or "blockaddress(" in row:
                safe[name] = False
            if row == "}":
                name = ""
        elif row.startswith("declare "):
            symbols = online_runtime_symbols(row)
            if len(symbols) != 1 or symbols[0] == "":
                fail("online runtime import encountered an unsupported declaration", 0)
            declared[symbols[0]] = True
            other.append(row.replace("dso_local ", ""))
        elif not row.startswith("@"):
            if len(online_runtime_symbols(row)) > 0:
                fail("online runtime import encountered a global metadata reference", 0)
            other.append(row)
    if name != "":
        fail("online runtime import encountered an incomplete function", 0)
    # External functions are valid host boundaries whether their bodies are
    # importable or not. Private dependencies require a fixed-point check.
    for name in bodies:
        for ref in refs[name]:
            if ref not in bodies and ref not in declared:
                safe[name] = False
        for ref in online_runtime_symbols(bodies[name][0])[1:]:
            if ref in bodies and not public[ref]:
                safe[name] = False
        for row in bodies[name][1:]:
            symbols = online_runtime_symbols(row)
            for ref in symbols:
                if ref in bodies and not public[ref]:
                    direct = (" call " in row or " invoke " in row) and symbols[0] == ref and symbols.count(ref) == 1 and "@" + ref + "(" in row
                    if not direct:
                        safe[name] = False
    changed = True
    while changed:
        changed = False
        for name in bodies:
            if safe[name]:
                for ref in refs[name]:
                    if ref in bodies and not public[ref] and not safe[ref]:
                        safe[name] = False
                        changed = True
    for name in bodies:
        body = bodies[name]
        if safe[name]:
            if public[name]:
                other.append("define available_externally " + body[0][7:].replace("dso_local ", "").replace("dso_preemptable ", ""))
                other = other + body[1:]
            else:
                other = other + body
        elif public[name]:
            other.append(online_runtime_declaration(body[0]))
    return "\n".join(other) + "\n"
