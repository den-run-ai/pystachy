"""Experimental Python-free baseline + runtime scalar region specialization.

Compile this tool with Pystachy; native_dynamic_check.py prepares its C loader.
The host invokes a native compiler and LLVM tools, never a Python subprocess.
"""
import math
import os
import sys
import tempfile
import time
from ffi import extern, c_void_p, c_int64
from tools.native_dynamic_vm import Program, Dyn, dyn_int, dyn_float, dyn_bool, dyn_str, dyn_none, dyn_repr
from tools.native_dynamic_types import NativeTypes
from src.pystachy_compiler.driver import q, sh


@extern("libpsdyn.so")
def psdyn_load(path: str) -> c_void_p: ...


@extern("libpsdyn.so")
def psdyn_call(handle: c_void_p, i0: c_int64, i1: c_int64, i2: c_int64,
               f0: float, f1: float, f2: float) -> c_int64: ...


@extern("libpsdyn.so")
def psdyn_result_i(handle: c_void_p) -> c_int64: ...


@extern("libpsdyn.so")
def psdyn_result_f(handle: c_void_p) -> float: ...


class Dispatcher:
    def __init__(self, source: str, mode: str, compiler: str, llvm: str, prepared: str,
                 warmup: int, max_variants: int, max_attempts: int):
        self.program = Program(source, max_steps=0)
        self.source = source
        self.mode = mode
        self.compiler = compiler
        self.llvm = llvm
        self.prepared = prepared
        self.warmup = warmup
        self.max_variants = max_variants
        self.max_attempts = max_attempts
        self.directory: str = tempfile.mkdtemp()
        self.profiles: dict[str, int] = {}
        self.handles: dict[str, int] = {}
        self.rejected: dict[str, bool] = {}
        self.baseline = 0
        self.native = 0
        self.misses = 0
        self.failures = 0
        self.rejections = 0
        self.attempts = 0
        self.compile_seconds = 0.0

    def signature(self, name: str, args: list[Dyn]) -> str:
        return name + ":" + ",".join([x.tag for x in args])

    def compile(self, name: str, args: list[Dyn], key: str) -> None:
        self.attempts += 1
        start = time.perf_counter()
        try:
            ret = NativeTypes(self.program).function(name, [x.tag for x in args])
        except (ValueError, KeyError):
            self.rejected[key] = True
            self.rejections += 1
            self.compile_seconds += time.perf_counter() - start
            return
        stem = self.directory + "/variant" + str(self.attempts)
        params = ["a" + str(i) + ": " + args[i].tag for i in range(len(args))]
        actual = [("i" if args[i].tag == "int" else "f") + str(i) for i in range(len(args))]
        setter = "pys_dynamic_result_i" if ret == "int" else "pys_dynamic_result_f"
        code = self.source + "\n\ndef _psdyn_result(" + ", ".join(params) + ") -> " + ret + ":\n"
        code += "    return " + name + "(" + ", ".join(["a" + str(i) for i in range(len(args))]) + ")\n"
        code += "\ndef pys_dynamic_result_i(v: int) -> None: ...\n"
        code += "\ndef pys_dynamic_result_f(v: float) -> None: ...\n"
        code += "\ndef pys_dynamic_entry(i0: int, i1: int, i2: int, f0: float, f1: float, f2: float) -> int:\n"
        code += "    try:\n        " + setter + "(_psdyn_result(" + ", ".join(actual) + "))\n"
        code += "        return " + ("1" if ret == "int" else "2") + "\n    except Exception:\n        return -1\n"
        with open(stem + ".py", "w") as f:
            f.write(code)
        cmd = q(self.compiler) + " rt " + q(stem + ".py") + " -o " + q(stem + ".ll")
        cmd += " && " + q(self.llvm + "/llvm-link") + " " + q(self.prepared + "/image.bc")
        cmd += " " + q(stem + ".ll") + " --only-needed " + q(self.prepared + "/runtime.bc") + " -o " + q(stem + ".bc")
        cmd += " && " + q(self.llvm + "/opt") + " -passes='internalize,default<O2>'"
        cmd += " -internalize-public-api-list=psdyn_image_call,psdyn_image_i,psdyn_image_f " + q(stem + ".bc") + " -o " + q(stem + ".bc")
        cmd += " && " + q(self.llvm + "/clang") + " -O2 -fPIC -shared " + q(stem + ".bc") + " -o " + q(stem + ".so") + " -lm -ldl"
        status = sh("(" + cmd + ") > " + q(stem + ".log") + " 2>&1")
        handle = psdyn_load(stem + ".so") if status == 0 else 0
        if handle == 0:
            self.failures += 1
            self.rejected[key] = True
        else:
            self.handles[key] = handle
        self.compile_seconds += time.perf_counter() - start

    def call(self, name: str, args: list[Dyn]) -> Dyn:
        if name not in self.program.functions:
            raise ValueError("unknown function: " + name)
        if len(args) != len(self.program.functions[name].kids[0].kids):
            raise TypeError("argument count mismatch")
        key = self.signature(name, args)
        eligible = self.mode == "adaptive" and len(args) <= 3
        for x in args:
            if x.tag not in ["int", "float"] or (x.tag == "float" and not math.isfinite(x.real)):
                eligible = False
        if eligible and key in self.handles:
            ints = [x.integer if x.tag == "int" else 0 for x in args] + [0, 0, 0]
            floats = [x.real if x.tag == "float" else 0.0 for x in args] + [0.0, 0.0, 0.0]
            status = psdyn_call(self.handles[key], ints[0], ints[1], ints[2], floats[0], floats[1], floats[2])
            if status == 1 or status == 2:
                self.native += 1
                return dyn_int(psdyn_result_i(self.handles[key])) if status == 1 else dyn_float(psdyn_result_f(self.handles[key]))
            self.misses += 1  # pure whole-region replay, including checked overflow/division
        elif self.mode == "adaptive":
            self.misses += 1
        self.baseline += 1
        result = self.program.execute(name, args)
        # Finite signature domain: 1+2+4+8 numeric tuples per function; rare types
        # cannot reserve a profile or compilation slot ahead of a later hot tuple.
        if eligible:
            self.profiles[key] = self.profiles.get(key, 0) + 1
            if self.profiles[key] >= self.warmup and key not in self.handles and key not in self.rejected:
                if len(self.handles) < self.max_variants and self.attempts < self.max_attempts:
                    self.compile(name, args, key)
        return result

    def close(self) -> None:
        # Loaded scalar images live to process exit; discard their private build files.
        for i in range(1, self.attempts + 1):
            for suffix in [".py", ".ll", ".bc", ".so", ".log"]:
                path = self.directory + "/variant" + str(i) + suffix
                if os.path.exists(path):
                    os.remove(path)
        os.rmdir(self.directory)


def parse_value(s: str) -> Dyn:
    i = s.find(":")
    tag = s[:i] if i >= 0 else s
    value = s[i + 1:] if i >= 0 else ""
    if tag == "int":
        return dyn_int(int(value))
    if tag == "float":
        return dyn_float(float(value))
    if tag == "bool" and value in ["true", "false"]:
        return dyn_bool(value == "true")
    if tag == "str":
        return dyn_str(value)
    if tag == "None" and value == "":
        return dyn_none()
    raise ValueError("invalid tagged argument: " + s)


def main() -> None:
    if len(sys.argv) < 7:
        raise ValueError("usage: native_dynamic SOURCE PLAN baseline|adaptive COMPILER LLVM PREPARED [WARMUP VARIANTS ATTEMPTS]")
    mode = sys.argv[3]
    if mode not in ["baseline", "adaptive"]:
        raise ValueError("mode must be baseline or adaptive")
    warmup = int(sys.argv[7]) if len(sys.argv) > 7 else 3
    variants = int(sys.argv[8]) if len(sys.argv) > 8 else 2
    attempts = int(sys.argv[9]) if len(sys.argv) > 9 else 4
    if warmup < 1 or variants < 0 or attempts < 0:
        raise ValueError("invalid specialization budget")
    with open(sys.argv[1]) as f:
        source = f.read()
    with open(sys.argv[2]) as f:
        plan = f.read()
    dispatcher = Dispatcher(source, mode, sys.argv[4], sys.argv[5], sys.argv[6], warmup, variants, attempts)
    try:
        for line in plan.splitlines():
            words = line.split()
            if len(words) == 0 or words[0].startswith("#"):
                continue
            name = words[0]
            repeats = int(words[1])
            if repeats < 1:
                raise ValueError("repeat count must be positive")
            args = [parse_value(w) for w in words[2:]]
            start = time.perf_counter()
            try:
                result = dyn_none()
                for _ in range(repeats):
                    result = dispatcher.call(name, args)
                elapsed = time.perf_counter() - start
                print("RESULT\t" + name + "\t" + result.tag + "\t" + dyn_repr(result) + "\t" + str(elapsed))
            except Exception as e:
                print("ERROR\t" + name + "\t" + repr(str(e)))
        print(f"STATS\tbaseline={dispatcher.baseline}\tnative={dispatcher.native}\tmisses={dispatcher.misses}\tfailures={dispatcher.failures}\trejections={dispatcher.rejections}\tattempts={dispatcher.attempts}\tcompile_seconds={dispatcher.compile_seconds}\tprofiles={len(dispatcher.profiles)}\tvariants={len(dispatcher.handles)}")
    finally:
        dispatcher.close()


if __name__ == "__main__":
    main()
