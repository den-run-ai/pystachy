#!/usr/bin/env python3
"""Reproduce the optional text-kernel experiment (Linux, clang/LLVM 18).

Run under an exclusive benchmark/build lock. Output directories must be new.
The dependency is a pristine Git snapshot, not the caller's working tree. Every
run has fresh private runtime caches and records all source/dependency hashes.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tarfile
import time

STRINGZILLA_COMMIT = "3cd0f9bcab97912dd36ca4ca4253f1f46b33ef8e"
ROOT = Path(__file__).resolve().parents[2]
VARIANTS = {
    "baseline": [],
    "float_span": ["-DPYSTACHY_FLOAT_SPAN"],
    "stringzilla": ["-DPYSTACHY_STRINGZILLA"],
    "combined": ["-DPYSTACHY_FLOAT_SPAN", "-DPYSTACHY_STRINGZILLA"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def witness(text: str) -> list[str]:
    """Retain every output field except measured nanoseconds."""
    result = []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] in ("first", "sample"):
            if len(fields) != 3:
                raise ValueError(f"unexpected timing record: {line}")
            int(fields[-1])
            result.append(" ".join(fields[:-1]))
        else:
            result.append(line)
    return result


def measure(text: str) -> int:
    samples = [int(line.split()[-1]) for line in text.splitlines() if line.startswith("sample ")]
    if len(samples) != 1 or samples[0] < 0:
        raise ValueError("expected exactly one nonnegative timed sample")
    return samples[0]


class Run:
    def __init__(self, output: Path, compiler: Path, dependency: Path, cpu: int):
        self.output, self.compiler, self.dependency = output, compiler, dependency
        if any(c.isspace() for c in str(output)):
            raise ValueError("output path cannot contain whitespace (PYSTACHY_CFLAGS splits on whitespace)")
        output.mkdir(parents=True, exist_ok=False)
        self.log = output / "commands.log"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM"}
        self.env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PATH=str(ROOT / "ports"), PYTHONPATH=str(ROOT / "ports"))
        llvm = self.env.get("PYSTACHY_LLVM", "")
        self.clang = str(Path(llvm) / "clang") if llvm else "clang"
        self.linker = str(Path(llvm) / "llvm-link") if llvm else "llvm-link"
        os.sched_setaffinity(0, {cpu})
        self.metadata: dict = {
            "base_commit": "f7103067545b43cdcd8ce20dc66b1571425b3a8d",
            "source_head": self.call(["git", "rev-parse", "HEAD"]).stdout.strip(),
            "compiler_sha256": digest(compiler),
            "python": sys.version, "platform": platform.platform(), "cpu_affinity": [cpu],
            "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                               if line.startswith("model name")), "unknown"),
            "clang": self.call([self.clang, "--version"]).stdout,
            "source_hashes": {}, "variants": {}, "samples": [], "checks": [],
        }
        paths = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
        for name in sorted(set(paths)):
            path = ROOT / name
            if path.is_file():
                self.metadata["source_hashes"][name] = digest(path)

    def call(self, command: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
        start = time.perf_counter_ns()
        result = subprocess.run(command, cwd=ROOT, env=env or self.env, capture_output=True, text=True)
        with self.log.open("a") as stream:
            stream.write(json.dumps({"command": command, "returncode": result.returncode,
                                     "elapsed_ns": time.perf_counter_ns() - start}) + "\n")
            stream.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"command failed ({result.returncode}): {command}; see {self.log}")
        return result

    def prepare(self) -> None:
        archive = self.output / "stringzilla-source.tar"
        self.call(["git", "-C", str(self.dependency), "archive", "--format=tar", f"--output={archive}",
                   STRINGZILLA_COMMIT, "include", "LICENSE", "VERSION"])
        snapshot = self.output / "dependency"
        snapshot.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(snapshot, filter="data")
        hashes = {str(p.relative_to(snapshot)): digest(p) for p in sorted(snapshot.rglob("*")) if p.is_file()}
        lib = self.output / "libtextkernels.so"
        start = time.perf_counter_ns()
        self.call([self.clang, "-O2", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
                   str(ROOT / "tools/text_kernels/stringzilla_adapter.c"), f"-I{snapshot / 'include'}", "-o", str(lib)])
        library = ctypes.CDLL(str(lib))
        library.pystachy_stringzilla_backend.restype = ctypes.c_char_p
        self.metadata["dependency"] = {
            "repository": "https://github.com/ashvardanian/StringZilla", "commit": STRINGZILLA_COMMIT,
            "archive_sha256": digest(archive), "files_sha256": hashes,
            "adapter_build_ns": time.perf_counter_ns() - start, "adapter_bytes": lib.stat().st_size,
            "adapter_sha256": digest(lib), "backend": library.pystachy_stringzilla_backend().decode(),
        }
        for name, defines in VARIANTS.items():
            flags = defines.copy()
            if name in ("stringzilla", "combined"):
                flags += [f"-L{self.output}", "-ltextkernels", f"-Wl,-rpath,{self.output}"]
            env = self.env | {"PYSTACHY_CFLAGS": " ".join(flags), "PYSTACHY_CACHE": str(self.output / name / "cache")}
            (self.output / name).mkdir()
            self.metadata["variants"][name] = {"flags": flags, "env": env, "builds": {}}
        self.save()

    def save(self) -> None:
        # Keep only relevant configuration, not unrelated inherited environment.
        copy = json.loads(json.dumps(self.metadata))
        for variant in copy.get("variants", {}).values():
            variant["env"] = {k: v for k, v in variant["env"].items() if k.startswith("PYSTACHY_") or k == "PYTHONPATH"}
        (self.output / "results.json").write_text(json.dumps(copy, indent=2) + "\n")

    def build(self, name: str, source: Path, label: str) -> Path:
        variant = self.metadata["variants"][name]
        exe = self.output / name / label
        start = time.perf_counter_ns()
        self.call([str(self.compiler), "build", str(source), "-o", str(exe)], variant["env"])
        variant["builds"][label] = {"elapsed_ns": time.perf_counter_ns() - start, "executable_bytes": exe.stat().st_size,
                                     "sha256": digest(exe)}
        self.save()
        return exe

    def correctness(self) -> None:
        fixtures = [ROOT / "tests/programs/numbers/float_span.py", ROOT / "tests/programs/library/json_bulk_unicode.py"]
        for name in VARIANTS:
            env = self.metadata["variants"][name]["env"]
            for source in fixtures:
                oracle = self.call([sys.executable, str(source)])
                expected = oracle.stdout
                if oracle.stderr or expected + "[exit 0]\n" != source.with_suffix(".out").read_text():
                    raise AssertionError(f"recording changed: {source}")
                exe = self.build(name, source, source.stem)
                for tier, command, settings in [
                    ("aot", [str(exe)], env),
                    ("jit", [str(self.compiler), "run", str(source)], env),
                    ("aot-gc-stress", [str(exe)], env | {"PYSTACHY_GC_STRESS_PROGRAM": "1", "PYSTACHY_GC_STRESS": "1"}),
                ]:
                    result = self.call(command, settings)
                    if result.stdout != expected or result.stderr:
                        raise AssertionError(f"differential mismatch: {name} {source.stem} {tier}")
                    self.metadata["checks"].append([name, source.stem, tier, "CPython exact stdout; empty stderr"])
                print("checked", name, source.stem, flush=True)
        self.save()

    def probes(self) -> None:
        rt = self.output / "runtime-py.ll"
        self.call([str(self.compiler), "rt", str(ROOT / "runtime.py"), "-o", str(rt)])
        for name in ("baseline", "combined"):
            flags = self.metadata["variants"][name]["flags"]
            for source in (ROOT / "tools/bytescanprobe.c", ROOT / "tools/text_kernels/float_probe.c"):
                stem = source.stem
                ir, bc, exe = (self.output / name / (stem + suffix) for suffix in (".ll", ".bc", ""))
                defines = [flag for flag in flags if flag.startswith("-D")]
                self.call([self.clang, "-O2", "-S", "-emit-llvm", *defines, str(source), "-o", str(ir)])
                self.call([self.linker, str(rt), str(ir), "-o", str(bc)])
                self.call([self.clang, "-O2", str(bc), "-o", str(exe), "-lm", *flags])
                result = self.call([str(exe)])
                (self.output / name / f"{stem}.out").write_text(result.stdout)
                self.metadata["checks"].append([name, stem, result.stdout])
                if stem == "bytescanprobe":
                    self.call([str(exe)], self.env | {"PYSTACHY_GC_STRESS": "1"})
                print("probe", name, stem, flush=True)
        self.save()

    def benchmarks(self, repeats: int) -> None:
        sources = {"json": ROOT / "bench/extended/json_scan.py", "numeric": ROOT / "bench/text_kernels/numeric_load.py"}
        binaries = {(name, kind): self.build(name, source, kind) for name in VARIANTS for kind, source in sources.items()}
        cases = []
        for mode in ("direct", "repair"):
            for case, size, calls in [("short", 8, 100000), ("long", 8192, 2000), ("unicode", 4096, 150),
                                      ("sparse", 8192, 2000), ("dense", 256, 300)]:
                cases.append((f"json-{mode}-{case}", "json", [mode, case, str(size), str(calls), "1", "1"]))
        for case, calls in [("short", 200000), ("plain", 3000), ("long", 1000), ("trimmed", 3000),
                            ("underscores", 1000), ("unicode", 1000)]:
            cases.append((f"numeric-{case}", "numeric", [case, str(calls), "1", "1"]))
        for label, kind, args in cases:
            oracle = witness(self.call([sys.executable, str(sources[kind]), *args]).stdout)
            for repeat in range(repeats):
                names = list(VARIANTS)
                # Rotate ordering to reduce monotonic host-load/temperature bias.
                names = names[repeat % len(names):] + names[:repeat % len(names)]
                for name in names:
                    result = self.call([str(binaries[name, kind]), *args], self.metadata["variants"][name]["env"])
                    if witness(result.stdout) != oracle or result.stderr:
                        raise AssertionError(f"benchmark oracle mismatch: {label} {name}")
                    self.metadata["samples"].append({"case": label, "variant": name, "repeat": repeat,
                                                      "nanoseconds": measure(result.stdout), "witness": oracle})
                self.save()
            print("measured", label, flush=True)
        medians = {}
        for label, _, _ in cases:
            medians[label] = {name: statistics.median(row["nanoseconds"] for row in self.metadata["samples"]
                                                    if row["case"] == label and row["variant"] == name) for name in VARIANTS}
        self.metadata["median_nanoseconds"] = medians
        self.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy")
    parser.add_argument("--stringzilla-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--checks-only", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    run = Run(args.output.resolve(), args.compiler.resolve(), args.stringzilla_source.resolve(), args.cpu)
    run.prepare()
    run.correctness()
    run.probes()
    if not args.checks_only:
        run.benchmarks(args.repeats)
    print(run.output / "results.json")


if __name__ == "__main__":
    main()
