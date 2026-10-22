"""Ported pyperformance 1.14.0 benchmarks; see bench/pyperformance/README.md.

The controller runs on CPython. Each benchmark is an adapted upstream file whose main prints
deterministic results to stdout and, to stderr, the seconds of the part that pyperf would time
(TIMED_PART). Every JIT and AOT run must print exactly what CPython printed, or the run fails.
Timings are advisory: there are no thresholds. --census reads the pinned sdist, replaces each
upstream file's pyperf runner with a direct call of its benchmark, reports the first compiler
error, and checks each port's notes and timed part against the upstream file.
"""
import argparse
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shlex
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

from bench_extended import execute

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench" / "pyperformance"
SDIST_SHA256 = "91f74393997b604375ad5b79bf569a24076d70181c076a53abad5383a238a8aa"
SDIST_DIR = "pyperformance-1.14.0/pyperformance/data-files/benchmarks/"

# The ported benchmarks: the arguments of a measured run (sized for most of a second of
# CPython 3.13 on an idle 2.1 GHz x86-64 core), and of a --smoke run (correctness only).
# bench/pyperformance/NAME.py's main reads them; each starts with the number of loops.
BENCHMARKS = {
    "barnes_hut": (["1"], ["1", "5", "50"]),
    "chaos": (["10"], ["1", "200"]),
    "fannkuch": (["2"], ["1", "7"]),
    "float": (["10"], ["1", "1000"]),
    "go": (["4"], ["1"]),
    "hexiom": (["100"], ["1"]),
    "meteor_contest": (["6"], ["1"]),
    "nbody": (["10"], ["1", "100"]),
    "nqueens": (["10"], ["1", "6"]),
    "raytrace": (["4"], ["1", "20", "20"]),
    "regex_dna": (["4"], ["1", "1000"]),
    "regex_effbot": (["20"], ["1"]),
    "regex_v8": (["20"], ["1"]),
    "richards": (["20"], ["1"]),
    "richards_super": (["20"], ["1"]),
    "scimark": (["2"], ["1"]),
    "spectral_norm": (["10"], ["1"]),
    "unpack_sequence": (["50000"], ["1"]),
}

# Excluded from the delivered suite pending a separate provenance decision.
DEFERRED = {"deltablue": "license provenance"}

# SHA-256 of each upstream bm_NAME/run_benchmark.py tried, ported or not: the 31 that this port
# set out to try, and the other 21 that need no third-party package (bench/pyperformance/README.md).
UPSTREAM = {
    "2to3": "a491c6dfe070a073cae07fc07f903afcc6d795207f2c70ab96f0ac0d9363d916",
    "argparse": "f914991901e5a24d536753c3b2b5229b1e9e5d4d982ba82da2e1cfbbf3677feb",
    "async_generators": "0441979a5ffc49c1e44539f5cb5a082bb70fcef5627619872feb4f3901351de5",
    "async_tree": "7c1493bc27c5c41f70f51cbf46a33c77b791915364ce619231461441f042178b",
    "asyncio_tcp": "fa993861ad75dcd724d282442e671095ad708a9dcb87e4314831d04006ad4a23",
    "barnes_hut": "802a1c170b82a5d82ea69b7a893f09d4b50b4f232e20a8e1c1bb8b2c04e6af1d",
    "base64": "e2f1e7d4dbfbb2c722833081496497344550e4367f85f67f373fb8aa22cd35ed",
    "bpe_tokeniser": "c7255345499e118181785370b0996e8cc1056491b9678b3fbeb02421e3f9b2df",
    "chaos": "5d20fd29c8ea89e0ebe4040ae4c05f26f1a620cd2a7fc654d9d7f8cb205651ac",
    "comprehensions": "6047efc06287a24a646f00fc8a8d47429f7cdeab3e942230e13cf6d7cefa6343",
    "concurrent_imap": "d5bfb854e7a1d754f3033132dca397704ea7ed2aabfd6d625396b61b82a9e316",
    "coroutines": "9358a7d967ed16859b5a163a4e416d897d6f104b3603c56ad77903791211fc7f",
    "crypto_pyaes": "236222412fd81b5e13d9c818574b575809eccff17419d667f34cf0e9148aa724",
    "decimal_factorial": "0b88119beb7a2151ef59f0d7d969e655850d9aeef143426efd0e0a656b2bbcc6",
    "decimal_pi": "eb3974785e602143f16fcfbd07ffd8b742b326096d9fd914c59a79531175104c",
    "deepcopy": "9e1550442cbccfaff8a4988936487c091ac18bcc9c8ebdc41c1cb747c14ea078",
    "deltablue": "70da5e16cd5b14f2f398ccc066794b83a30d997c2d91150695b8f938f934dc30",
    "fannkuch": "2a8e4bc4c5e7e8ac605a4ca8246cc4baeab5336ac986d976e33657162750e8bf",
    "float": "b4f61a0978f5b0af2c0d07544ae26422868992e62b8f40e2967e3c694fc1b9a9",
    "gc_collect": "7886042f07e517abb79c58643a4b488710f3079936c6990522624bfb9c2acb9b",
    "gc_traversal": "0798ab87ca12687c68e101d14ae9ac0c50eaa9b4f14ecee3882f7e499191828f",
    "generators": "46c59dc44cb63b2c0fed75e6d82875daa237a92d03c87861078513c7b10d4621",
    "go": "ea4c0ebaf32515f8549c64c9291ab13d47bb802e01a82203c37b5066d1bfb463",
    "hexiom": "d7518220380d27449b8951bc9ca2e19593569d9bd9f5cb6d86867f354f22e115",
    "json_dumps": "023c991ff827fdcbfcfb2b7e3cadf023352a61d1903643d8af0ef302a0db1bf7",
    "json_loads": "16c41ff06bf3173d30158c767340d389c459a656e997e306719891d50f09646f",
    "logging": "6ff62fdc4c6b520b01475407b526ed609299402ed8ad8d344038b559a120159a",
    "mdp": "3db5bfb8c9e2602f181cee809c24b2bd61e7c088e89e8e22867b8d46c4d0fcf1",
    "meteor_contest": "b616f5f87e129a6b35650452951f40a7812cf22efff5a0777e51287da13c2f48",
    "nbody": "d1385e816d7cfea361b7915e2cf70138cd6b84f40df8bd5152638851f7bcac2b",
    "nqueens": "f50ef0d82036790c99f5469b9cffc368e097de860231b328caa6652183af059e",
    "pathlib": "113a1cbbec13165dfdb84db649d8114279460110733957a3749ffb9c9527612d",
    "pickle": "31c0e30be79514b45db0d4e858632eb429b0fea3edbac6463ad5f34d92f3cab8",
    "pidigits": "4bf89183acb8651623676ece6e10787b6c71eec549fe53ce17a62a812ef7447d",
    "pprint": "07ef57201c7919aedf9e340c7fb1561a40dfee698818c9694930f3e427091d6d",
    "pyflate": "ec5347c7045af86ba33e1b2c6f64bc4b506d0ade3b77391d7e41863fe25fb464",
    "python_startup": "4cc396c9fe32d633a5e902c8ca738391a4cfe80b6d7658a9d9048989fc796d0c",
    "raytrace": "88ef4d9060d8e8f6ce40f376477aaf89cc808fa44813225a3071a05a1467f017",
    "regex_compile": "cdbc509e515840e469209ed5fc77ca3fe352278203cc1a7dad874db4e863dc6c",
    "regex_dna": "d820dbdf12262cd11a543ae3dc3fd85793a20220d5a15ef687d8ef57a75c97c6",
    "regex_effbot": "0823b6507f8babea2238847562d9c9af31000ea57cbb695e5d47053321ea68c7",
    "regex_v8": "c22f820cb9a031a892ec0341eecca81c758dc25ee5413613d18eddfdff54a491",
    "richards": "a4512668525331960c54043b5150a3fff92badaeaba850a941893ac69a1028d8",
    "richards_super": "665b3d5551171e147c127b6f8671edc9a7703c736d317cc4a991bb00f599dc36",
    "scimark": "427b21b8a3802418ea3c2fe584335658a6c91c7f74fce4df9410efa60cd84d6e",
    "spectral_norm": "a3390ec6d75606fec30c4b59ad5f77d5292cd8e36f445197232a34560a880b18",
    "sqlite_synth": "dcba7a6889e66f08480f4332860208d624678fc42a03be5c8f3b6f1f894231fd",
    "telco": "a3acb202b3d4eb750aca977ce354f8ecc1f6adae17a695ed2e5be615e4797605",
    "tomli_loads": "a94f7368f9656044f45244eb71da4f29a785c154c4a75aa15ca5c0e3c609c0d0",
    "typing_runtime_protocols": "dfc0cbd25f2968ee6982ff93adde92a1fa2a56ffbed6dde2d1f9cb853c340961",
    "unpack_sequence": "0dafe97531abc4a5baf30fe011db7acb3bf1e64cd4e41acb0c7db2bb141a8382",
    "xml_etree": "1d824c4d4dd92a7598e085dbdf7beed3809a75e4d6972c90377822c78f73477c",
}

# --census: the statements that stand in for each upstream main, calling what its pyperf
# runner would time with the default arguments.
CENSUS_CALLS = {
    "2to3": ("datadir = os.path.join(os.path.dirname(__file__), 'data', '2to3')\n"
             "pyfiles = glob.glob(os.path.join(datadir, '*.py.txt'))\n"
             "subprocess.run([sys.executable, '-m', 'lib2to3', '-f', 'all'] + pyfiles, check=True)"),
    "argparse": "for name in sorted(BENCHMARKS):\n    BENCHMARKS[name]()",
    "async_generators": "bench_async_generators()",
    "async_tree": "asyncio.run(BENCHMARKS['none'](use_task_groups=False).run())",
    "asyncio_tcp": "asyncio.run(main(False))",
    "barnes_hut": "bench_quadtree_nbody(1, DEFAULT_PARTICLES, DEFAULT_ITERATIONS, DEFAULT_THETA)",
    "base64": ("for bench in (bench_b64_small, bench_b64_large, bench_urlsafe_b64_small, bench_b32_small,\n"
               "              bench_b32_large, bench_b16_small, bench_b16_large, bench_a85_small,\n"
               "              bench_a85_large, bench_b85_small, bench_b85_large):\n    bench(1)"),
    "bpe_tokeniser": "bench_bpe_tokeniser(1)",
    "chaos": "main(None, None)",
    "comprehensions": "bench_comprehensions(1)",
    "concurrent_imap": "bench_mp_pool(2, 1000, 10)\nbench_thread_pool(2, 1000, 10)",
    "coroutines": "bench_coroutines(1)",
    "crypto_pyaes": "bench_pyaes(1)",
    "decimal_factorial": "bench_decimal_factorial()",
    "decimal_pi": "bench_decimal_pi()",
    "deepcopy": "benchmark(1)\nbenchmark_reduce(1)\nbenchmark_memo(1)",
    "deltablue": "delta_blue(100)",
    "fannkuch": "fannkuch(DEFAULT_ARG)",
    "float": "benchmark(POINTS)",
    "gc_collect": "benchamark_collection(1, CYCLES, LINKS)",
    "gc_traversal": "benchamark_collection(1, N_LEVELS)",
    "generators": "bench_generators(1)",
    "go": "versus_cpu()",
    "hexiom": "main(1, DEFAULT_LEVEL)",
    "json_dumps": "bench_json_dumps([(obj, range(count)) for obj, count in [EMPTY, SIMPLE, NESTED, HUGE]])",
    "json_loads": "bench_json_loads((json.dumps(DICT), json.dumps(TUPLE), json.dumps(DICT_GROUP)))",
    "logging": ("stream = io.StringIO()\nhandler = logging.StreamHandler(stream=stream)\n"
                "logger = logging.getLogger('benchlogger')\nlogger.propagate = False\n"
                "logger.addHandler(handler)\nlogger.setLevel(logging.WARNING)\n"
                "for bench in sorted(BENCHMARKS):\n    BENCHMARKS[bench](1, logger, stream)"),
    "mdp": "bench_mdp(1)",
    "meteor_contest": ("board, cti, pieces = get_puzzle(WIDTH, HEIGHT)\n"
                       "bench_meteor_contest(1, board, pieces, SOLVE_ARG,\n"
                       "                     get_footprints(board, cti, pieces), get_senh(board, cti))"),
    "nbody": "bench_nbody(1, DEFAULT_REFERENCE, DEFAULT_ITERATIONS)",
    "nqueens": "bench_n_queens(8)",
    "pathlib": "tmp_path = setup(NUM_FILES)\ntry:\n    bench_pathlib(1, tmp_path)\nfinally:\n    shutil.rmtree(tmp_path)",
    "pickle": ("import pickle\nimport types\noptions = types.SimpleNamespace(protocol=pickle.HIGHEST_PROTOCOL)\n"
               "for name in sorted(BENCHMARKS):\n    BENCHMARKS[name][0](1, pickle, options)"),
    "pidigits": "calc_ndigits(DEFAULT_DIGITS)",
    "pprint": "p.pformat(printable)",
    "pyflate": "bench_pyflake(1, os.path.join(os.path.dirname(__file__), 'data', 'interpreter.tar.bz2'))",
    "python_startup": "import subprocess\nsubprocess.run([sys.executable, '-c', 'pass'], check=True)",
    "raytrace": "bench_raytrace(1, DEFAULT_WIDTH, DEFAULT_HEIGHT, None)",
    "regex_compile": "bench_regex_compile(1, capture_regexes())",
    "regex_dna": "bench_regex_dna(1, init_benchmarks(DEFAULT_INIT_LEN, DEFAULT_RNG_SEED), None)",
    "regex_effbot": "bench_regex_effbot(1)",
    "regex_v8": "bench_regex_v8(1)",
    "richards": "Richards().run(1)",
    "richards_super": "Richards().run(1)",
    "scimark": "for bench in sorted(BENCHMARKS):\n    BENCHMARKS[bench][0](1, *BENCHMARKS[bench][1:])",
    "spectral_norm": "bench_spectral_norm(1)",
    "sqlite_synth": "bench_sqlite(1)",
    "telco": "bench_telco(1, rel_path('data', 'telco-bench.b'))",
    "tomli_loads": "bench_tomli_loads(1)",
    "typing_runtime_protocols": "bench_protocols(1)",
    "unpack_sequence": "bench_all(1)",
    "xml_etree": ("import xml.etree.ElementTree as et\nfor bench in BENCHMARKS:\n"
                  "    bench_etree(1, et, globals()['bench_%s' % bench])"),
}


# What pyperf times in each ported benchmark, which --census reads from the upstream main: the
# function that runner.bench_func() calls, whose calls the port's main times in one loop; or the
# functions that time themselves for runner.bench_time_func(), each around one loop. The ports
# keep those timers in place with time.perf_counter(), which is pyperf.perf_counter(), and add
# their seconds to a list TIMED, whose sum the main prints.
TIMED_PART = {
    "barnes_hut": ["bench_quadtree_nbody"],
    "chaos": "create_image_chaos",
    "fannkuch": "fannkuch",
    "float": "benchmark",
    "go": "versus_cpu",
    "hexiom": ["main"],
    "meteor_contest": ["bench_meteor_contest"],
    "nbody": ["bench_nbody"],
    "nqueens": "bench_n_queens",
    "raytrace": ["bench_raytrace"],
    "regex_dna": ["bench_regex_dna"],
    "regex_effbot": ["bench_regex_effbot"],
    "regex_v8": ["bench_regex_v8"],
    "richards": "run",
    "richards_super": "run",
    "scimark": ["SparseCompRow_matmult", "bench_FFT", "bench_LU", "bench_MonteCarlo", "bench_SOR"],
    "spectral_norm": ["bench_spectral_norm"],
    "unpack_sequence": ["do_unpacking"],
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def census_source(text, call):
    """The upstream file without pyperf's import and main, calling its benchmark instead.

    Line numbers are kept up to the main, so the first error names the upstream line."""
    out = []
    for line in text.split("\n"):
        if re.match(r"if __name__ == ['\"]__main__['\"]:", line):
            break
        out.append("" if re.match(r"\s*(import pyperf|from pyperf import)", line) else line)
    body = "\n".join(out).rstrip().replace("pyperf.perf_counter()", "time.perf_counter()")
    return body + "\n\n\nimport time  # noqa: E402\n\nif __name__ == \"__main__\":\n" + \
        "".join("    " + line + "\n" for line in call.split("\n"))


def first_error(output):
    """The first line of a compiler's messages, without the chain of calls that reached it."""
    line = output.strip().split("\n")[0] if output.strip() else ""
    return re.sub(r" \(compiling .*\)$", "", line).replace(" (specializing ", " (")


def unmarked_hunks(upstream, port):
    """Hunks of the port's diff from upstream that no "Pystachy port" line explains.

    A note explains its own hunk and one that starts within three lines; the note of the
    main that replaces pyperf's runner explains every change after it."""
    old, new = upstream.split("\n"), port.split("\n")
    main = [i for i, line in enumerate(new) if "Pystachy port: a deterministic main replaces" in line]
    out = []
    for group in difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(1):
        changed = [(j1, j2) for tag, _, _, j1, j2 in group if tag != "equal"]
        lo, hi = changed[0][0], max(j2 for _, j2 in changed)
        if not any("Pystachy port" in line for line in new[max(0, lo - 3):hi + 1]) and not (main and lo > main[0]):
            out.append(f"{lo + 1}-{max(hi, lo + 1)}")
    return out


def called(node):
    """The names of the functions and methods that NODE calls."""
    return {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            for n in ast.walk(node) if isinstance(n, ast.Call)}


def timers(tree, clock):
    """{function: (timer statements, statements between the first and the last)} for each function
    whose body calls CLOCK.perf_counter()."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            marks = [i for i, s in enumerate(node.body) if f"{clock}.perf_counter()" in ast.unparse(s)]
            if marks:
                out[node.name] = (len(marks), node.body[marks[0] + 1:marks[-1]])
    return out


def upstream_timed_part(text):
    """TIMED_PART's entry for an upstream file, and what keeps its timers from fitting the rule."""
    tree = ast.parse(text)
    targets = {ast.unparse(n.args[1]).split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == "bench_func" and len(n.args) > 1}
    own = timers(tree, "pyperf")
    problems = [f"{name}(): its timer is not around one loop" for name, (count, between) in sorted(own.items())
                if count != 2 or len(between) != 1 or not isinstance(between[0], ast.For)]
    if targets and own or len(targets) > 1:
        problems.append("both bench_func() and its own timers, or several bench_func() targets")
    return (min(targets) if targets else sorted(own)), problems


def timing_errors(name, text):
    """How port NAME's printed seconds differ from what pyperf times (TIMED_PART); empty if not."""
    spec, tree, errors = TIMED_PART[name], ast.parse(text), []
    own = timers(tree, "time")
    value, region = None, None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        for k, stmt in enumerate(body if isinstance(body, list) else []):
            if isinstance(stmt, ast.Expr) and ast.unparse(stmt).startswith("print('seconds', "):
                value = ast.unparse(stmt.value.args[1])
                starts = [i for i in range(k) if ast.unparse(body[i]) == "t0 = time.perf_counter()"]
                region = body[starts[-1] + 1:k] if starts else None
    if isinstance(spec, str):
        if own:
            errors.append(f"functions with their own timer: {', '.join(sorted(own))}")
        if value != "time.perf_counter() - t0" or region is None:
            errors.append("the main does not print the seconds since its t0 = time.perf_counter()")
        elif len(region) != 1 or not isinstance(region[0], ast.For) or len(region[0].body) != 1:
            errors.append("the main times more than one loop of one statement")
        elif spec not in called(region[0].body[0]):
            errors.append(f"the main's timed loop does not call {spec}()")
    else:
        if sorted(own) != sorted(spec):
            errors.append(f"functions with their own timer: {', '.join(sorted(own)) or 'none'}; "
                          f"expected {', '.join(spec)}")
        for function, (count, between) in sorted(own.items()):
            if count != 2 or len(between) != 1 or not isinstance(between[0], ast.For):
                errors.append(f"{function}(): the timer is not around one loop")
        if value != "sum(TIMED)" or region is not None:
            errors.append("the main does not print sum(TIMED), without a timer of its own")
        if "TIMED.append(" not in text:
            errors.append("no function adds its seconds to TIMED")
    return errors


def census(args, compiler, env):
    data = Path(args.census).read_bytes()
    if digest(data) != SDIST_SHA256:
        raise RuntimeError(f"{args.census}: SHA-256 {digest(data)}, expected {SDIST_SHA256}")
    rows = []
    with tarfile.open(args.census) as tar, tempfile.TemporaryDirectory(prefix="pyperformance-census-") as tmp:
        for name in sorted(UPSTREAM):
            text = tar.extractfile(SDIST_DIR + f"bm_{name}/run_benchmark.py").read()
            if digest(text) != UPSTREAM[name]:
                raise RuntimeError(f"bm_{name}/run_benchmark.py: SHA-256 {digest(text)}, expected {UPSTREAM[name]}")
            source = text.decode("utf-8")
            path = Path(tmp) / f"bm_{name}.py"
            path.write_text(census_source(source, CENSUS_CALLS[name]))
            # (from the root, as tests/run.sh runs a compiler: "python3 -m pystachy" works too)
            result = subprocess.run(compiler + ["ir", str(path), "-o", os.devnull], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=args.timeout)
            output = (result.stdout + result.stderr).replace(str(path.parent) + os.sep, "")
            row = {"name": name, "ported": name in BENCHMARKS,
                   "deferred": DEFERRED.get(name, ""),
                   "compile_status": "compiled" if result.returncode == 0 else "error",
                   "first_error": first_error(output) if result.returncode else "",
                   "returncode": result.returncode}
            if name in BENCHMARKS:
                port = (BENCH / f"{name}.py").read_text()
                row["unmarked_hunks"] = unmarked_hunks(source, port)
                spec, problems = upstream_timed_part(source)
                if spec != TIMED_PART[name]:
                    problems.append(f"pyperf times {spec}, not {TIMED_PART[name]} (TIMED_PART)")
                row["timing"] = problems + timing_errors(name, port)
            rows.append(row)
    print("| Benchmark | Status | First compiler error of the upstream file |")
    print("|---|---|---|")
    for row in rows:
        error = row["first_error"].replace("|", "\\|") or "none: compiles"
        status = ("ported" if row["ported"] else "deferred: " + row["deferred"] if row["deferred"]
                  else "runner-only compiles; not ported" if row["returncode"] == 0 else "blocked")
        print(f"| `{row['name']}` | {status} | `{error}` |")
    failures = [f"{r['name']}: hunks without a 'Pystachy port' note at lines {', '.join(r['unmarked_hunks'])}"
                for r in rows if r.get("unmarked_hunks")]
    failures += [f"{r['name']}: {problem}" for r in rows for problem in r.get("timing", [])]
    for failure in failures:
        print(failure, file=sys.stderr)
    return {"sdist_sha256": SDIST_SHA256, "benchmarks": rows}, not failures


def seconds(stderr):
    """The timed part's seconds that a benchmark's main prints to stderr."""
    found = re.findall(r"^seconds (\S+)$", stderr, re.M)
    if len(found) != 1:
        raise ValueError(f"expected one 'seconds' line on stderr: {stderr[-500:]!r}")
    value = float(found[0])
    if not value >= 0:
        raise ValueError(f"invalid seconds: {found[0]}")
    return value


def run(command, env, timeout, expected=None):
    """Run a benchmark process: wall, CPU (user + system) and in-process seconds."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    record = execute(command, env, timeout)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record["cpu_s"] = after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime
    record["loop_s"] = seconds(record["stderr"])
    if expected is not None and record["stdout"] != expected:
        raise ValueError(f"output differs from CPython's: {shlex.join(command)}\n"
                         f"expected: {expected[-500:]!r}\ngot: {record['stdout'][-500:]!r}")
    return record


def median(records, key):
    return statistics.median(r[key] for r in records)


def metadata(compiler, env, timeout):
    def info(command):
        try:
            return execute(command, env, timeout)["stdout"].strip()
        except (OSError, RuntimeError) as exc:
            return str(exc)
    return {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision": info(["git", "rev-parse", "HEAD"]),
        "git_status": info(["git", "status", "--porcelain"]),
        "platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(),
        "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "host_python": sys.version, "compiler_command": compiler,
        "compiler_binary_sha256": digest(Path(compiler[0]).read_bytes()) if Path(compiler[0]).is_file() else None,
        "environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_") or k == "PYTHONHASHSEED"},
        "sources_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes())
                           for p in sorted(BENCH.glob("*.py")) + [Path(__file__).resolve()]},
    }


def measure(name, arguments, args, compiler, env, directory):
    source = str(BENCH / f"{name}.py")
    exe = str(directory / name)
    commands = {"cpython": [sys.executable, source] + arguments,
                "jit": compiler + ["run", source] + arguments,
                "aot": [exe] + arguments}
    oracle = run(commands["cpython"], env, args.timeout)
    build = execute(compiler + ["build", source, "-o", exe], env, args.timeout)
    # PYSTACHY_GC_STRESS_PROGRAM=N stresses the JIT's program; an executable reads
    # PYSTACHY_GC_STRESS, as tests/run.sh sets it
    stress = env.get("PYSTACHY_GC_STRESS_PROGRAM", "")
    envs = {"cpython": env, "jit": env, "aot": dict(env, PYSTACHY_GC_STRESS=stress) if stress else env}
    runs = {mode: [] for mode in commands}
    for repeat in range(args.runs):
        # rotate the order of the modes from one repetition to the next; never in parallel
        modes = ["cpython", "jit", "aot"]
        for mode in modes[repeat % 3:] + modes[:repeat % 3]:
            runs[mode].append(run(commands[mode], envs[mode], args.timeout, oracle["stdout"]))
    summary = {mode: {key: median(records, key) for key in ("wall_s", "cpu_s", "loop_s")}
               for mode, records in runs.items()}
    for mode, records in runs.items():
        # how far apart the runs were, and the least CPU time a process had of its wall time
        walls = [r["wall_s"] for r in records]
        summary[mode]["wall_spread"] = (max(walls) - min(walls)) / summary[mode]["wall_s"] if min(walls) > 0 else 0.0
        summary[mode]["cpu_share_min"] = min((r["cpu_s"] / r["wall_s"] for r in records if r["wall_s"] > 0),
                                             default=0.0)
    return {"name": name, "arguments": arguments, "output": oracle["stdout"],
            "aot_build_s": build["wall_s"], "summary": summary, "runs": runs}


def conditions(results):
    """The largest spread of a mode's wall times ((max - min) / median) and the least share of its
    wall time that a process spent on a CPU, each with where it occurred."""
    cells = [(s[key], key, f"{r['name']} {mode}") for r in results for mode, s in r["summary"].items()
             for key in ("wall_spread", "cpu_share_min")]
    spread = max((c for c in cells if c[1] == "wall_spread"), default=(0.0, "", ""))
    share = min((c for c in cells if c[1] == "cpu_share_min"), default=(0.0, "", ""))
    return {"wall_spread": {"value": spread[0], "where": spread[2]},
            "cpu_share_min": {"value": share[0], "where": share[2]}}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="shell-split command, no shell evaluation")
    parser.add_argument("--benchmarks", nargs="+", choices=sorted(BENCHMARKS), default=sorted(BENCHMARKS))
    parser.add_argument("--runs", type=positive, default=5, help="processes per mode and benchmark")
    parser.add_argument("--smoke", action="store_true", help="small sizes, one run: correctness only")
    parser.add_argument("--census", metavar="SDIST", help="pyperformance-1.14.0.tar.gz: first errors of the upstream files")
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds per command, including LLVM children")
    parser.add_argument("--json", type=Path, help="report (default build/pyperformance.json, or -smoke/-census)")
    args = parser.parse_args(argv)
    if not args.timeout > 0 or args.timeout == float("inf"):
        parser.error("timeout must be positive and finite")
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    if "/" in compiler[0]:
        compiler[0] = str((ROOT / compiler[0]).resolve())
    if args.smoke:
        args.runs = 1
    suffix = "-census" if args.census else "-smoke" if args.smoke else ""
    args.json = args.json or ROOT / "build" / f"pyperformance{suffix}.json"
    env = dict(os.environ)
    env.setdefault("PYTHONHASHSEED", "0")
    if args.census:
        # Measure the shipped module surface, independently of caller overlays.
        env.pop("PYSTACHY_PATH", None)
    report = {"schema_version": 1, "status": "running", "settings": {
        k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    try:
        report["metadata"] = metadata(compiler, env, args.timeout)
        if args.census:
            result, ok = census(args, compiler, env)
            report.update(result)
            report["status"] = "ok" if ok else "failed"
        else:
            report["benchmarks"] = []
            with tempfile.TemporaryDirectory(prefix="pyperformance-") as tmp:
                warm = Path(tmp) / "warm.py"
                warm.write_text("pass\n")
                # (the first run may build the runtime cache: it is not timed)
                execute(compiler + ["run", str(warm)], env, args.timeout)
                print("| Benchmark | Arguments | CPython | JIT | AOT | CPython/AOT | "
                      "CPython timed | JIT timed | AOT timed | AOT build |")
                print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
                for name in args.benchmarks:
                    arguments = BENCHMARKS[name][1 if args.smoke else 0]
                    report["active"] = name
                    result = measure(name, arguments, args, compiler, env, Path(tmp))
                    report["benchmarks"].append(result)
                    s = result["summary"]
                    cells = [s[m]["wall_s"] for m in ("cpython", "jit", "aot")]
                    ratio = cells[0] / cells[2] if cells[2] > 0 else 0.0
                    timed = [s[m]["loop_s"] for m in ("cpython", "jit", "aot")]
                    print(f"| `{name}` | {' '.join(arguments)} | " + " | ".join(f"{v:.3f}" for v in cells) +
                          f" | {ratio:.1f}x | " + " | ".join(f"{v:.4f}" for v in timed) +
                          f" | {result['aot_build_s']:.1f} |", flush=True)
                del report["active"]
            report["status"] = "ok"
            report["metadata"]["load_average_end"] = os.getloadavg() if hasattr(os, "getloadavg") else None
            if not args.smoke:
                report["conditions"] = conditions(report["benchmarks"])
                spread, share = report["conditions"]["wall_spread"], report["conditions"]["cpu_share_min"]
                print(f"Largest spread of wall times: {spread['value']:.0%} ({spread['where']}); least CPU time "
                      f"of a process's wall time: {share['value']:.0%} ({share['where']})")
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        report["status"], report["error"] = "failed", str(exc)
        print(f"pyperformance benchmark failed: {exc}", file=sys.stderr)
    finally:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Raw report: {args.json}", file=sys.stderr)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
