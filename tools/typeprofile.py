"""Type-feedback census: how skewed are the dynamic types at the call sites of ordinary Python?

usage: python3 tools/typeprofile.py record OUT.json [--eligibility ADAPTIVE.py] (-m MODULE | SCRIPT) [ARG ...]
       python3 tools/typeprofile.py time OUT.json (-m MODULE | SCRIPT) [ARG ...]
       python3 tools/typeprofile.py report RECORDING.json ... [--json SUMMARY.json]

record runs a program under CPython's sys.monitoring (PEP 669, CPython 3.12+) and counts every
Python function entry by its call site, the function entered and its arguments' types. A type is
both shallow, the class a polymorphic inline cache keys on, and deep: containers are summarized by
sampling up to three items, the form a Pystachy template specialization would need. Each call also
records two contexts: the caller's own call site (a call string of depth 2) and the caller's deep
argument types (the caller specialized for its arguments, as in customization and selective
specialization). Return types, and the field types of instances when their __init__ returns or one
of their methods is entered, are counted too. Each deep type is judged against Pystachy's type rules
(docs/language/typing.md). With --eligibility, each function entered is also checked against the
source subset of the adaptive prototype at that path (PR #374's tools/adaptive.py).

time runs the program under cProfile, in a separate process, for each function's own and inclusive
time; report joins it with a recording of the same program when both are given.

report prints, for each recording, the share of calls at monomorphic, polymorphic (2-4 entries) and
megamorphic (more than 4) sites at each context depth, the share that a site's one or two most
common entries cover, type expressibility, return and field stability, and the most polymorphic sites.
Recording slows a program by roughly 5-20x; only its counts are reported, never its timings.
"""
import collections
import json
import os
import runpy
import sys
import sysconfig
import types

I64_MIN, I64_MAX = -(1 << 63), (1 << 63) - 1
STDLIB = (os.path.realpath(sysconfig.get_paths()["stdlib"]) + os.sep,)
# Instances of these library classes have Pystachy counterparts (lib/README.md, docs/language.md).
SUPPORTED_CLASSES = {"re.Pattern", "re.Match", "_io.StringIO", "_io.TextIOWrapper", "difflib.SequenceMatcher",
                     "difflib.Match", "textwrap.TextWrapper", "string.Template", "_csv.reader", "_csv.writer",
                     "csv.DictReader", "csv.DictWriter"}
CALLABLES = (types.FunctionType, types.BuiltinFunctionType, types.MethodType, types.BuiltinMethodType,
             types.LambdaType, types.MethodWrapperType, types.WrapperDescriptorType, types.MethodDescriptorType)
KEY_ATOMS = {"int", "str", "bool"}
CONTAINERS = (list, tuple, set, frozenset, dict)
SETTLE = {"list", "dict", "set", "frozenset"}  # a tuple's length is part of its type
SAMPLE_FIELDS = 16  # one method entry in 16 samples its instance's fields
IMPORT_HOOKS = os.sep + "_distutils_hack" + os.sep  # setuptools' meta path finder runs at every import


class Recorder:
    """Counts calls by (callee, site, parent site, caller signature, shallow signature, deep signature)."""

    def __init__(self, skip):
        self.skip = skip  # code filenames never recorded: this tool and the import machinery
        self.codes = {}
        self.code_rows = []
        self.code_objects = []
        self.sites = {}
        self.sigs = {}
        self.names = {type(None): "None", bool: "bool", float: "float", str: "str", int: "int"}
        self.names.update((t, t.__name__) for t in CONTAINERS)
        self.reasons = {"int": "", "None": "", "bool": "", "float": "", "str": "", "int>64": "int beyond 64 bits"}
        for t in CONTAINERS:  # empty, and nested beyond the sampling depth: typed by context, or unknown
            self.reasons[t.__name__ + "[]"] = self.reasons[t.__name__ + "[?]"] = ""
        self.calls = collections.Counter()
        self.returns = collections.Counter()
        self.fields = collections.Counter()
        self.frames = {}
        self.entries = collections.Counter()

    # -- types -------------------------------------------------------------------------------

    def type_name(self, t):
        name = self.names.get(t)
        if name is None:
            name, reason = self.judge_class(t)
            self.names[t] = name
            self.reasons[name] = reason
        return name

    def judge_class(self, t):
        qual = f"{t.__module__}.{t.__qualname__}"
        if issubclass(t, BaseException):
            return "exc:" + qual, ""
        if t in (bytes, bytearray, memoryview):
            return t.__name__, "bytes"
        if t is complex:
            return "complex", "complex"
        if t is type or issubclass(t, type):
            return "type", "class object"
        if t is types.ModuleType:
            return "module", "module"
        if t is object:
            return "object", "object sentinel"
        if issubclass(t, CALLABLES):
            return "callable", ""
        if t in (range, types.GeneratorType, types.CoroutineType) or "iterator" in t.__name__:
            return qual, "iterator or generator"
        if qual in SUPPORTED_CLASSES:
            return qual, ""
        module = sys.modules.get(t.__module__)
        path = (module.__dict__.get("__file__") if module is not None else None) or ""
        if not t.__flags__ & (1 << 9) or t.__module__ in sys.stdlib_module_names or os.path.realpath(path).startswith(STDLIB):
            return "lib:" + qual, "library class " + qual
        if any(getattr(base, "__name__", "") == "Enum" for base in t.__mro__):
            return "C:" + qual, "enum"
        bases = [b for b in t.__mro__[1:] if b is not object and b.__name__ != "Generic"]
        if bases and not (bases == [tuple] and "_fields" in t.__dict__):
            return "C:" + qual, "inheritance"
        return "C:" + qual, ""

    def deep(self, v, depth):
        t = type(v)
        if t is int:
            return "int" if I64_MIN <= v <= I64_MAX else "int>64"
        if t not in CONTAINERS:
            return self.type_name(t)
        if depth >= 2:
            return t.__name__ + "[?]"
        if t is tuple:
            if len(v) <= 9:
                return self.typed("tuple[" + ",".join(self.deep(x, depth + 1) for x in v) + "]", "tuple", [self.deep(x, depth + 1) for x in v])
            items = self.settle({self.deep(v[0], depth + 1), self.deep(v[len(v) // 2], depth + 1), self.deep(v[-1], depth + 1)})
            return self.typed("tuple[" + "|".join(sorted(items)) + ",...]", "long tuple", items)
        if t is list:
            if not v:
                return "list[]"
            items = self.settle({self.deep(v[0], depth + 1), self.deep(v[len(v) // 2], depth + 1), self.deep(v[-1], depth + 1)})
            return self.typed("list[" + "|".join(sorted(items)) + "]", "list", items)
        if t is set or t is frozenset:
            if not v:
                return t.__name__ + "[]"
            it = iter(v)
            items = self.settle({self.deep(next(it), depth + 1) for _ in range(min(3, len(v)))})
            return self.typed(t.__name__ + "[" + "|".join(sorted(items)) + "]", "set", items)
        if t is dict:
            if not v:
                return "dict[]"
            # Iteration only: a lookup could run a key's own __hash__ and __eq__.
            keys = self.settle({self.deep(next(iter(v)), depth + 1), self.deep(next(reversed(v)), depth + 1)})
            values = self.settle({self.deep(next(iter(v.values())), depth + 1), self.deep(next(reversed(v.values())), depth + 1)})
        return self.typed("dict[" + "|".join(sorted(keys)) + ":" + "|".join(sorted(values)) + "]", "dict", (keys, values))

    @staticmethod
    def settle(items):
        """Drop an empty or unsampled list, dict or set among items that hold a sampled one of its
        kind: Pystachy types an empty container from its context."""
        kinds = {t.split("[", 1)[0] for t in items if t.split("[", 1)[0] in SETTLE and not t.endswith(("[]", "[?]"))}
        return {t for t in items if not (t.endswith(("[]", "[?]")) and t.split("[", 1)[0] in kinds)}

    def typed(self, name, kind, items):
        if name not in self.reasons:
            self.reasons[name] = self.container_reason(kind, items)
        return name

    def container_reason(self, kind, items):
        def element(members, what):
            real = set(members) - {"None"}
            if len(real) > 1:
                return "mixed " + what
            if not real:
                return what + " of None only"
            return next((self.reasons.get(m, "") for m in real if self.reasons.get(m, "")), "")

        def key(members):
            for m in members:
                atoms = m[len("tuple["):-1].split(",") if m.startswith("tuple[") else [m]
                if any(a not in KEY_ATOMS and a != "None" for a in atoms) or (m == "None"):
                    return "unsupported key type " + m
            return "mixed keys" if len(members) > 1 else ""

        if kind == "tuple":
            return next((self.reasons.get(m, "") for m in items if self.reasons.get(m, "")), "")
        if kind == "long tuple":
            return "tuple longer than nine items"
        if kind == "list":
            return element(items, "list")
        if kind == "set":
            return key(items)
        keys, values = items
        return key(keys) or element(values, "dict values")

    def signature(self, sig):
        index = self.sigs.get(sig)
        if index is None:
            index = self.sigs[sig] = len(self.sigs)
        return index

    # -- events ------------------------------------------------------------------------------

    def code_index(self, code):
        if code.co_filename in self.skip or code.co_filename.startswith("<frozen") or IMPORT_HOOKS in code.co_filename:
            self.codes[code] = -1
            return -1
        index = self.codes[code] = len(self.code_rows)
        flags = code.co_flags
        nargs = code.co_argcount + code.co_kwonlyargcount + bool(flags & 4) + bool(flags & 8)
        self.code_rows.append({"file": code.co_filename, "line": code.co_firstlineno, "name": code.co_name,
                               "qualname": code.co_qualname, "params": list(code.co_varnames[:nargs]),
                               "generator": bool(flags & 0x2a0),
                               "stdlib": os.path.realpath(code.co_filename).startswith(STDLIB)})
        self.code_objects.append(code)
        return index

    def site_index(self, frame):
        key = (frame.f_code, frame.f_lasti)
        index = self.sites.get(key)
        if index is None:
            index = self.sites[key] = len(self.sites)
        return index

    def on_start(self, code, offset):
        index = self.codes.get(code)
        if index is None:
            index = self.code_index(code)
        if index < 0:
            return sys.monitoring.DISABLE
        frame = sys._getframe(1)
        caller = frame.f_back
        site = parent = caller_sig = -1
        if caller is not None:
            site = self.site_index(caller)
            known = self.frames.get(id(caller))
            if known is not None and known[0] is caller.f_code:
                parent, caller_sig = known[1], known[2]
        local = frame.f_locals
        values = []
        for name in self.code_rows[index]["params"]:
            try:
                values.append(local[name])
            except KeyError:
                values.append(None)
        shallow = self.signature(tuple(self.type_name(type(v)) for v in values))
        deep = self.signature(tuple(self.deep(v, 0) for v in values))
        self.calls[index, site, parent, caller_sig, shallow, deep] += 1
        self.frames[id(frame)] = (code, site, deep, index)
        count = self.entries[index] = self.entries[index] + 1
        if values and count % SAMPLE_FIELDS == 1 and self.code_rows[index]["params"][0] == "self":
            self.sample_fields(values[0])
        return None

    def on_return(self, code, offset, value):
        frame = sys._getframe(1)
        known = self.frames.pop(id(frame), None)
        if known is None or known[0] is not code:
            return None
        self.returns[known[3], known[2], self.deep(value, 0)] += 1
        if code.co_name == "__init__" and self.code_rows[known[3]]["params"][:1] == ["self"]:
            try:
                self.sample_fields(frame.f_locals["self"])
            except KeyError:
                pass
        return None

    def on_unwind(self, code, offset, exception):
        self.frames.pop(id(sys._getframe(1)), None)

    def sample_fields(self, obj):
        # Never run the program's code: getattr could call a class's own __getattr__.
        try:
            attrs = object.__getattribute__(obj, "__dict__")
        except AttributeError:
            return
        if type(attrs) is not dict:
            return
        owner = self.type_name(type(obj))
        for name, value in list(attrs.items())[:32]:
            self.fields[owner, name, self.deep(value, 0)] += 1

    # -- output ------------------------------------------------------------------------------

    def dump(self, path, program, eligibility, status):
        sites = [None] * len(self.sites)
        for (code, offset), index in self.sites.items():
            sites[index] = {"file": code.co_filename, "name": code.co_qualname, "offset": offset,
                            "line": next((line for start, end, line in code.co_lines() if start <= offset < end), None)}
        sigs = [None] * len(self.sigs)
        for sig, index in self.sigs.items():
            sigs[index] = list(sig)
        if eligibility:
            for row, code in zip(self.code_rows, self.code_objects):
                row["adaptive"] = eligible(eligibility, code)
        report = {"program": program, "status": status, "python": sys.version.split()[0], "codes": self.code_rows, "sites": sites,
                  "sigs": sigs, "reasons": self.reasons,
                  "calls": [list(k) + [n] for k, n in self.calls.items()],
                  "returns": [list(k) + [n] for k, n in self.returns.items()],
                  "fields": [list(k) + [n] for k, n in self.fields.items()]}
        with open(path, "w", encoding="utf-8") as out:
            json.dump(report, out)


def eligible(source_check, code):
    """'' if the adaptive prototype's source subset accepts this function, else its reason."""
    if code.co_freevars:
        return "closures are outside the prototype"
    try:
        source_check(types.FunctionType(code, {"__builtins__": __builtins__}))
    except Exception as error:
        return str(error) or type(error).__name__
    return ""


def load_source_check(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("_typeprofile_adaptive", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._source


def run_target(argv):
    """Run the program as python3 would; return its exit status. An uncaught exception is
    reported as CPython reports it, since some workloads end with one by design."""
    try:
        if argv[0] == "-m":
            sys.argv = argv[1:]
            runpy.run_module(argv[1], run_name="__main__", alter_sys=True)
        else:
            sys.argv = argv
            sys.path.insert(0, os.path.dirname(os.path.abspath(argv[0])))
            runpy.run_path(argv[0], run_name="__main__")
    except SystemExit as stop:
        if stop.code is None or isinstance(stop.code, int):
            return stop.code or 0
        print(stop.code, file=sys.stderr)
        return 1
    except BaseException:
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sys.stdout.flush()
    return 0


def record(out, argv, eligibility_path):
    source_check = load_source_check(eligibility_path) if eligibility_path else None
    import pkgutil  # noqa: F401  run_path imports it; keep its import out of the recording
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    recorder = Recorder({__file__, runpy.__file__})
    mon.use_tool_id(tool, "typeprofile")
    mon.register_callback(tool, mon.events.PY_START, recorder.on_start)
    mon.register_callback(tool, mon.events.PY_RETURN, recorder.on_return)
    mon.register_callback(tool, mon.events.PY_UNWIND, recorder.on_unwind)
    mon.set_events(tool, mon.events.PY_START | mon.events.PY_RETURN | mon.events.PY_UNWIND)
    try:
        status = run_target(argv)
    finally:
        mon.set_events(tool, 0)
        mon.free_tool_id(tool)
    recorder.dump(out, argv, source_check, status)
    return status


def time_program(out, argv):
    import cProfile
    import pstats
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        status = run_target(argv)
    finally:
        profiler.disable()
    stats = pstats.Stats(profiler).stats
    rows = [{"file": f, "line": line, "name": name, "calls": nc, "own_s": tt, "inclusive_s": ct}
            for (f, line, name), (cc, nc, tt, ct, _) in stats.items()]
    total = sum(row["own_s"] for row in rows)
    with open(out, "w", encoding="utf-8") as stream:
        json.dump({"program": argv, "status": status, "total_s": total, "functions": rows}, stream)
    return status


# -- report ------------------------------------------------------------------------------------

EMPTY = {"list[]": "list[*]", "dict[]": "dict[*]", "set[]": "set[*]", "frozenset[]": "frozenset[*]"}


def normal(t):
    """A deep type as Pystachy would join it: None joins any type (T | None), an empty container
    takes its items' type from context, and None alternatives inside a container are optional items."""
    if t == "None":
        return "*"
    if t in EMPTY:
        return EMPTY[t]
    return t.replace("|None]", "]").replace("|None:", ":").replace("[None|", "[").replace(":None|", ":")


def compatible(a, b):
    return a == b or a == "*" or b == "*" or (a.endswith("[*]") and b.startswith(a[:-2])) or \
        (b.endswith("[*]") and a.startswith(b[:-2]))


def merge(a, b):
    return b if a == "*" or a.endswith("[*]") else a


def join_groups(counter, sigs):
    """Sizes of the groups of signatures that can share one Pystachy specialization, largest first."""
    groups = []
    for sig, n in counter.most_common():
        types = [normal(t) for t in sigs[sig]]
        for group in groups:
            if len(group[0]) == len(types) and all(compatible(a, b) for a, b in zip(group[0], types)):
                group[0] = [merge(a, b) for a, b in zip(group[0], types)]
                group[1] += n
                break
        else:
            groups.append([types, n])
    return sorted((g[1] for g in groups), reverse=True)


def shares(groups, total, sizes=lambda counter: sorted(counter.values(), reverse=True)):
    """Call shares by the number of distinct entries at each key, and the top-1/top-2 coverage."""
    mono = poly = mega = top1 = top2 = 0
    for counter in groups.values():
        best = sizes(counter)
        n, k = sum(best), len(best)
        if k == 1:
            mono += n
        elif k <= 4:
            poly += n
        else:
            mega += n
        top1 += best[0]
        top2 += sum(best[:2])
    return {"keys": len(groups), "mono": mono / total, "poly": poly / total, "mega": mega / total,
            "top1": top1 / total, "top2": top2 / total}


def summarize(data, timing=None, scope="program"):
    """Metrics over calls to program code (the default: not the standard library) or all code."""
    codes, sites, sigs, reasons = data["codes"], data["sites"], data["sigs"], data["reasons"]
    keep = [scope == "all" or not row["stdlib"] for row in codes]
    method = [row["params"][:1] in (["self"], ["cls"]) for row in codes]
    calls = [c for c in data["calls"] if keep[c[0]]]
    total = sum(c[-1] for c in calls)
    if not total:
        return None
    # (name, key, entry, joined): a key's entries are its distinct shallow or deep signatures, or
    # with joined, the groups of deep signatures that one Pystachy specialization could share.
    views = [
        # An inline cache's key: the target, and for a method its receiver's class (as CPython's
        # LOAD_ATTR/CALL specializations and Self's PICs cache); plain calls dispatch on the target.
        ("send site: target and receiver class", lambda c: (c[1],),
         lambda c: (c[0], sigs[c[4]][:1] if method[c[0]] else []), False),
        ("send site: target and classes", lambda c: (c[1],), lambda c: (c[0], c[4]), False),
        ("function: classes", lambda c: (c[0],), lambda c: c[4], False),
        ("function: deep types", lambda c: (c[0],), lambda c: c[5], False),
        ("function: Pystachy types", lambda c: (c[0],), lambda c: c[5], True),
        ("function + call site: Pystachy types", lambda c: (c[0], c[1]), lambda c: c[5], True),
        ("function + call string of 2: Pystachy types", lambda c: (c[0], c[1], c[2]), lambda c: c[5], True),
        ("function + caller's types: Pystachy types", lambda c: (c[0], c[1], c[3]), lambda c: c[5], True),
    ]
    result = {"program": data["program"], "scope": scope, "calls": total, "functions": len({c[0] for c in calls})}
    # Each view is weighted by calls, and with a timing run also by time: a call weighs its
    # function's own time per call under cProfile, which shows where specialization would pay.
    weights = {"views": lambda c: c[-1]}
    per_call = None
    if timing:
        own = {(f["file"], f["line"], f["name"]): f for f in timing["functions"]}
        per_call = []
        for row in codes:
            f = own.get((row["file"], row["line"], row["name"]))
            per_call.append(f["own_s"] / f["calls"] if f and f["calls"] else 0.0)
        if sum(c[-1] * per_call[c[0]] for c in calls) > 0:
            weights["views_time"] = lambda c: c[-1] * per_call[c[0]]
            result["program_time_share"] = sum(c[-1] * per_call[c[0]] for c in calls) / timing["total_s"]
    for label, weight in weights.items():
        result[label] = {}
        for name, key, value, joined in views:
            groups = collections.defaultdict(collections.Counter)
            for c in calls:
                if name.startswith("send site") and c[1] < 0:
                    continue
                entry = value(c)
                groups[key(c)][(entry[0], tuple(entry[1])) if name.endswith("receiver class") else entry] += weight(c)
            groups = {k: g for k, g in groups.items() if sum(g.values()) > 0}
            sizes = (lambda counter: join_groups(counter, sigs)) if joined else (lambda counter: sorted(counter.values(), reverse=True))
            weighed = sum(sum(g.values()) for g in groups.values())
            result[label][name] = shares(groups, weighed, sizes) if weighed else None

    # Specializations: joined (function, Pystachy signature) groups needed to cover 95% and 99% of calls.
    pairs = collections.Counter()
    by_function = collections.defaultdict(collections.Counter)
    for c in calls:
        pairs[c[0], c[5]] += c[-1]
        by_function[c[0]][c[5]] += c[-1]
    ranked = sorted((n for counter in by_function.values() for n in join_groups(counter, sigs)), reverse=True)
    result["specializations"] = {}
    for target in (0.95, 0.99):
        acc = needed = 0
        for n in ranked:
            if acc >= target * total:
                break
            acc += n
            needed += 1
        result["specializations"][f"{target:.0%}"] = needed
    result["distinct_function_signatures"] = len(pairs)

    # Expressibility: every argument's deep type has a Pystachy type.
    def sig_reason(sig_index):
        for t in sigs[sig_index]:
            if reasons.get(t, "unknown"):
                return reasons.get(t, "unknown")
        return ""
    why = collections.Counter()
    expressible = 0
    for c in calls:
        reason = sig_reason(c[5])
        if reason:
            why[reason] += c[-1]
        else:
            expressible += c[-1]
    result["args_expressible"] = expressible / total
    # The ext ABI (docs/ffi.md) passes positional int, float, bool and str values, and returns those or None.
    scalar = {"int", "float", "bool", "str"}
    result["ext_abi_args"] = sum(c[-1] for c in calls if all(t in scalar for t in sigs[c[5]])) / total
    result["unexpressible_reasons"] = {k: v / total for k, v in why.most_common(8)}
    if "views_time" in weights:
        weight = weights["views_time"]
        weighed = sum(weight(c) for c in calls)
        result["args_expressible_time"] = sum(weight(c) for c in calls if not sig_reason(c[5])) / weighed
        result["ext_abi_args_time"] = sum(weight(c) for c in calls if all(t in scalar for t in sigs[c[5]])) / weighed

    # Return types per (function, deep signature): one type, or a type and None (an optional).
    returns = collections.defaultdict(collections.Counter)
    for code, sig, rtype, n in data["returns"]:
        if keep[code]:
            returns[code, sig][rtype] += n
    rsigs = {t: [t] for counter in returns.values() for t in counter}
    stable = rtotal = rexpr = 0
    for counter in returns.values():
        n = sum(counter.values())
        rtotal += n
        if len(join_groups(counter, rsigs)) == 1:
            stable += n
        rexpr += sum(m for t, m in counter.items() if not reasons.get(t, "unknown"))
    result["returns_determined_by_arg_types"] = stable / rtotal if rtotal else None
    result["returns_expressible"] = rexpr / rtotal if rtotal else None

    # Fields: per (class, attribute), one type or a type and None.
    fields = collections.defaultdict(collections.Counter)
    for owner, attr, ftype, n in data["fields"]:
        if scope == "all" or owner.startswith("C:"):
            fields[owner, attr][ftype] += n
    fsigs = {t: [t] for counter in fields.values() for t in counter}
    fstable = ftotal = fexpr = 0
    for counter in fields.values():
        n = sum(counter.values())
        ftotal += n
        if len(join_groups(counter, fsigs)) == 1:
            fstable += n
        fexpr += sum(m for t, m in counter.items() if not reasons.get(t, "unknown"))
    result["field_samples"] = ftotal
    result["fields_stable"] = fstable / ftotal if ftotal else None
    result["fields_expressible"] = fexpr / ftotal if ftotal else None

    # The most polymorphic send sites by calls.
    by_site = collections.defaultdict(collections.Counter)
    for c in calls:
        if c[1] >= 0:
            by_site[c[1]][c[0], c[4]] += c[-1]
    worst = sorted(((sum(g.values()), s, g) for s, g in by_site.items() if len(g) > 1), key=lambda x: x[0], reverse=True)[:5]
    result["polymorphic_sites"] = [{"site": f"{os.path.basename(sites[s]['file'])}:{sites[s]['line']} {sites[s]['name']}",
                                    "calls": n / total, "entries": len(g),
                                    "top": [f"{codes[k[0]]['qualname']}({', '.join(sigs[k[1]])}) {m / n:.0%}" for k, m in g.most_common(3)]}
                                   for n, s, g in worst]

    # The adaptive prototype: calls it could run natively (accepted source; exact int/float arguments).
    if any("adaptive" in row for row in codes):
        native = sum(c[-1] for c in calls if codes[c[0]].get("adaptive") == "" and sigs[c[4]] and
                     all(t in ("int", "float") for t in sigs[c[5]]))
        result["adaptive_eligible_calls"] = native / total
        result["adaptive_eligible_functions"] = sum(1 for i, row in enumerate(codes) if keep[i] and row.get("adaptive") == "")
        if timing:
            own = {(f["file"], f["line"], f["name"]): f for f in timing["functions"]}
            per_code = collections.Counter()
            eligible_calls = collections.Counter()
            for c in calls:
                per_code[c[0]] += c[-1]
                if codes[c[0]].get("adaptive") == "" and sigs[c[5]] and all(t in ("int", "float") for t in sigs[c[5]]):
                    eligible_calls[c[0]] += c[-1]
            saved = sum(own.get((codes[i]["file"], codes[i]["line"], codes[i]["name"]), {}).get("own_s", 0) * n / per_code[i]
                        for i, n in eligible_calls.items())
            result["adaptive_eligible_time"] = saved / timing["total_s"] if timing["total_s"] else None
    return result


def fmt(x):
    return "–" if x is None else f"{x:.1%}"


def report(paths, out):
    summaries = []
    for path in paths:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
        timing_path = path[:-len(".json")] + ".time.json"
        timing = None
        if os.path.exists(timing_path):
            with open(timing_path, encoding="utf-8") as stream:
                timing = json.load(stream)
        for scope in ("program", "all"):
            summary = summarize(data, timing, scope)
            if summary is not None:
                summary["name"] = os.path.basename(path)[:-len(".json")]
                summaries.append(summary)
    for s in summaries:
        print(f"## {s['name']} ({s['scope']} code): {s['calls']:,} calls, {s['functions']} functions, "
              f"{s['distinct_function_signatures']} (function, deep signature) pairs")
        print("| view | keys | monomorphic | 2-4 | >4 | top-1 | top-2 |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for name, v in s["views"].items():
            if v is not None:
                print(f"| {name} | {v['keys']:,} | {fmt(v['mono'])} | {fmt(v['poly'])} | {fmt(v['mega'])} | {fmt(v['top1'])} | {fmt(v['top2'])} |")
        print(f"specializations for 95%/99% of calls: {s['specializations']['95%']}/{s['specializations']['99%']}; "
              f"arguments expressible: {fmt(s['args_expressible'])}; returns determined by argument types: "
              f"{fmt(s['returns_determined_by_arg_types'])}, expressible: {fmt(s['returns_expressible'])}; "
              f"fields stable: {fmt(s['fields_stable'])}, expressible: {fmt(s['fields_expressible'])}")
        if "adaptive_eligible_calls" in s:
            print(f"adaptive prototype: {s['adaptive_eligible_functions']} eligible functions, "
                  f"{fmt(s['adaptive_eligible_calls'])} of calls, {fmt(s.get('adaptive_eligible_time'))} of own time")
        print("unexpressible:", ", ".join(f"{k} {fmt(v)}" for k, v in s["unexpressible_reasons"].items()) or "none")
        for p in s["polymorphic_sites"][:3]:
            print(f"  {p['site']}: {fmt(p['calls'])} of calls, {p['entries']} entries: {'; '.join(p['top'])}")
        print()
    if out:
        with open(out, "w", encoding="utf-8") as stream:
            json.dump(summaries, stream, indent=1)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("record", "time", "report"):
        sys.exit(__doc__)
    command, rest = sys.argv[1], sys.argv[2:]
    if command == "report":
        out = ""
        if "--json" in rest:
            out = rest[rest.index("--json") + 1]
            rest = [a for a in rest if a not in ("--json", out)]
        report(rest, out)
        return
    out, argv = rest[0], rest[1:]
    eligibility_path = ""
    if argv[:1] == ["--eligibility"]:
        eligibility_path, argv = argv[1], argv[2:]
    if not argv:
        sys.exit(__doc__)
    sys.exit(record(out, argv, eligibility_path) if command == "record" else time_program(out, argv))


if __name__ == "__main__":
    main()
