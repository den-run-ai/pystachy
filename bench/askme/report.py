"""Render the tables of an AskMe benchmark result (bench.py's JSON) as Markdown.

usage: report.py RESULT.json > RESULT.md
"""

import json
import sys

ORDER = [
    "pystachy-aot",
    "pystachy-jit",
    "mypyc",
    "cpython",
    "pypy",
    "reference-cpython",
    "reference-pypy",
]
LABELS = {
    "pystachy-aot": "Pystachy AOT",
    "pystachy-jit": "Pystachy JIT",
    "mypyc": "mypyc + CPython",
    "cpython": "CPython",
    "pypy": "PyPy",
    "reference-cpython": "`askme.py` on CPython",
    "reference-pypy": "`askme.py` on PyPy",
}


def ms(value):
    return f"{value:,.0f}" if value >= 100 else f"{value:.1f}"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] + ["---:"] * (len(header) - 1)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as stream:
        report = json.load(stream)
    results = report["results"]
    runtimes = [name for name in ORDER if name in results["help"]]
    base = "cpython"

    def summary(workload, runtime):
        return results[workload][runtime]["summary"]

    def versus(workload, runtime):
        ratio = summary(workload, base)["wall_median_ms"] / summary(workload, runtime)["wall_median_ms"]
        return f"{ratio:.1f}x" if ratio >= 1 else f"{1 / ratio:.1f}x slower"

    out = []
    out.append("## Startup and short runs\n")
    out.append(
        "`--help` starts the program and exits. The suite is the sum of the median wall "
        f"times of {len(report['suite_scenarios'])} complete scripted runs "
        "(3 to 15 model requests each, some with shell actions).\n"
    )
    rows = []
    suite = report["suite_wall_median_ms"]
    for runtime in runtimes:
        rows.append(
            [
                LABELS[runtime],
                ms(summary("help", runtime)["wall_median_ms"]),
                ms(suite[runtime]),
                f"{suite[base] / suite[runtime]:.1f}x"
                if suite[runtime] <= suite[base]
                else f"{suite[runtime] / suite[base]:.1f}x slower",
                f"{summary('hello', runtime)['rss_median_mb']:.0f}",
            ]
        )
    out.append(
        table(["Runtime", "`--help` ms", "Suite ms", "Suite vs CPython", "Peak RSS MB"], rows)
    )

    steady = report["steady"]
    out.append("\n## Long runs\n")
    out.append(
        f"One scripted run of {steady['requests']:,} model requests "
        f"({steady['tasks']} tasks of {steady['steps']} steps: reads, searches, edits, writes and "
        "tree listings, no shell). *Navigation* scans 240-line files; *controller* uses tiny "
        "files, so prompt building, reply decoding and policy checks dominate. "
        "Per-step time excludes nothing: it is wall time divided by requests.\n"
    )
    rows = []
    for runtime in runtimes:
        nav = summary("steady", runtime)
        light = summary("light", runtime)
        rows.append(
            [
                LABELS[runtime],
                ms(nav["wall_median_ms"]),
                f"{nav['wall_median_ms'] / steady['requests']:.2f}",
                versus("steady", runtime),
                ms(light["wall_median_ms"]),
                f"{light['wall_median_ms'] / steady['requests']:.2f}",
                versus("light", runtime),
                f"{nav['rss_median_mb']:.0f}",
            ]
        )
    out.append(
        table(
            [
                "Runtime",
                "Navigation ms",
                "ms/step",
                "vs CPython",
                "Controller ms",
                "ms/step",
                "vs CPython",
                "Peak RSS MB",
            ],
            rows,
        )
    )

    transports = [
        (key, title)
        for key, title in (
            ("http", "HTTP"),
            ("http_curl", "HTTP, `curl`"),
            ("https", "HTTPS"),
            ("https_curl", "HTTPS, `curl`"),
        )
        if key in results
    ]
    if transports:
        requests = results[transports[0][0]]["requests"]
        out.append("\n## Real HTTP transport\n")
        out.append(
            f"The same kind of run ({requests} requests) against an instant loopback server "
            "instead of in-process replies: milliseconds per request, harness included. The "
            "port keeps one connection open and, in the `curl` columns, starts a `curl` "
            "process per request instead; `askme.py` calls `requests.post`, which opens a "
            "connection per request. TLS uses a 2048-bit RSA certificate from a private CA.\n"
        )
        rows = []
        for runtime in runtimes:
            cells = []
            for key, _title in transports:
                if runtime in results[key]:
                    cells.append(f"{summary(key, runtime)['wall_median_ms'] / requests:.2f}")
                else:
                    cells.append("")
            if any(cells):
                rows.append([LABELS[runtime]] + cells)
        out.append(table(["Runtime"] + [title for _key, title in transports], rows))

    out.append("\n## Per-scenario medians (ms)\n")
    header = ["Scenario"] + [LABELS[runtime] for runtime in runtimes]
    rows = []
    for name in report["suite_scenarios"]:
        rows.append([name] + [ms(summary(name, runtime)["wall_median_ms"]) for runtime in runtimes])
    out.append(table(header, rows))

    builds = report["builds"]
    out.append("\n## Build cost\n")
    rows = []
    if "pystachy_aot_build_s" in builds:
        rows.append(
            [
                "Pystachy AOT",
                f"{builds['pystachy_aot_build_s']:.1f} s",
                f"{builds['pystachy_aot_bytes'] / 1e6:.2f} MB executable; links libc, libm and libgcc",
            ]
        )
    if "pystachy_jit_first_launch_s" in builds:
        # A launch far above the interpreters' is a compilation: the program cache
        # skips a program that declares @ffi.extern libraries.
        cached = summary("help", "pystachy-jit")["wall_median_ms"] < 1000
        rows.append(
            [
                "Pystachy JIT",
                f"{builds['pystachy_jit_first_launch_s']:.1f} s first launch",
                "later launches reuse the program cache"
                if cached
                else "every launch compiles: the program cache skips programs with `@ffi.extern`",
            ]
        )
    if "mypyc_build_s" in builds:
        rows.append(
            [
                "mypyc",
                f"{builds['mypyc_build_s']:.1f} s",
                f"{builds['mypyc_extension_bytes'] / 1e6:.2f} MB of extension modules; needs CPython",
            ]
        )
    lines = ["| Runtime | Build | Artifact |", "|---|---:|---|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    out.append("\n".join(lines))
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
