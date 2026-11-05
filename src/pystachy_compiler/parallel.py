"""Fail-closed native float-map proof; ordinary calls remain the fallback."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import dynamic_program
from src.pystachy_compiler.ir import IFn, Val
from src.pystachy_compiler.utils import identity_abi, lib_source


def kernel_reason(fn: IFn) -> str:
    # This is a worker-safety allowlist, not the ordinary effect summary. Even a
    # helper with an empty summary may mutate a hidden runtime cache. Accept no
    # helpers at all, and only bounded, acyclic scalar code with private locals.
    f = fn.f
    if f.ptypes != ["float"] or f.ret != "float" or fn.ps != [0]:
        return "needs one float argument and a float result"
    if identity_abi(f):
        return "numeric identity ABI"
    if fn.counted or fn.rdepth != "" or fn.pads or fn.coro or len(fn.tries) > 0:
        return "recursion, exception or coroutine state"
    if len(fn.blocks) == 0 or fn.blocks[0].label != "entry":
        return "missing kernel body"
    slots: dict[str, str] = {}
    for i in fn.slots:
        if i.op != "slot" or i.k != 0 or i.t not in ["float", "bool"] or len(i.r) != 1 or len(i.a) != 0 or len(i.b) != 0 or i.x != "":
            return "non-scalar local storage"
        name = f"%{i.s or 'h'}.{i.r[0]}"
        if name in slots:
            return "duplicate local storage"
        slots[name] = i.t
    at: dict[str, int] = {}
    for j in range(len(fn.blocks)):
        if fn.blocks[j].label in at:
            return "ambiguous block label"
        at[fn.blocks[j].label] = j
    for j in range(len(fn.blocks)):
        b = fn.blocks[j]
        if b.handler != "" or len(b.code) == 0:
            return "exception handler or empty block"
        for k in range(len(b.code)):
            i = b.code[k]
            if i.x != "" or i.k != 0:
                return "unsupported operation metadata"
            terminal = i.op == "br" or i.op == "cbr" or i.op == "ret"
            if terminal != (k == len(b.code) - 1):
                return "missing or misplaced terminator"
            if i.op not in ["br", "cbr", "phi"] and len(i.b) != 0:
                return "unexpected control-flow edges"
            if len(i.r) != (0 if terminal or i.op == "mem.store" else 1):
                return "invalid scalar result count"
            if i.op == "mem.load" or i.op == "mem.store":
                load = i.op == "mem.load"
                if len(i.a) != (1 if load else 2) or i.a[0].v not in slots:
                    return "memory outside private locals"
                t = slots[i.a[0].v]
                if i.s != "" or i.a[0].t != "*" + t or (i.t if load else i.a[1].t) != t or (not load and i.t != ""):
                    return "local storage type mismatch"
            elif i.op == "scalar.bin":
                if not ((i.t == "float" and i.s in ["fadd", "fsub", "fmul", "fneg"])
                        or (i.t == "bool" and i.s in ["and", "or", "xor"])):
                    return "unsupported scalar operation " + i.s
                if len(i.a) != (1 if i.s == "fneg" else 2) or any([a.t != i.t for a in i.a]):
                    return "scalar operand type mismatch"
            elif i.op == "num.cmp":
                if i.t != "bool" or i.s not in ["==", "!=", "<", "<=", ">", ">="] or len(i.a) != 2 or any([a.t != "float" for a in i.a]):
                    return "non-float comparison"
            elif i.op == "phi":
                if i.s != "" or i.t not in ["float", "bool"] or len(i.a) == 0 or len(i.a) != len(i.b) or any([a.t != i.t for a in i.a]):
                    return "non-scalar selection"
                if any([label not in at or at[label] >= j for label in i.b]):
                    return "loop or backward phi"
            elif i.op == "select":
                if i.s != "" or i.t not in ["float", "bool"] or len(i.a) != 3 or i.a[0].t != "bool" or any([a.t != i.t for a in i.a[1:]]):
                    return "non-scalar selection"
            elif i.op == "br" or i.op == "cbr":
                if i.t != "" or i.s != "" or len(i.b) != (1 if i.op == "br" else 2) or len(i.a) != (0 if i.op == "br" else 1) or (i.op == "cbr" and i.a[0].t != "bool"):
                    return "invalid branch"
                if any([label not in at or at[label] <= j for label in i.b]):
                    return "loop or backward edge"
            elif i.op == "ret":
                if i.t != "" or i.s != "" or len(i.a) != 1 or i.a[0].t != "float":
                    return "non-float return"
            else:
                return "unsupported operation " + i.op + (" " + i.s if i.s != "" else "")
            if any([a.v.startswith("@") for a in i.a]):
                return "global operand"
    return ""


def gen_parallel_maps(self) -> list[str]:
    # The normal frontend has already evaluated/captured the callable and all
    # arguments, including keyword/default handling. Match its immutable callable
    # constant, never the source name of an argument that may have been rebound.
    # This pass owns all its state; nothing survives a retry or compilation.
    name = "parallel$map_float"
    if self.rtmode or name not in self.funcs:
        return []
    lib = self.funcs[name]
    if not lib_source(lib.node.line, self.libdir, "parallel.py"):
        return []
    if dynamic_program():
        self.out.append("; parallel.map_float: serial (numeric identity program)")
        return []
    targets: dict[str, str] = {}
    for key in self.adapters:
        suffix = "] callable[float,float]"
        if key.startswith("fn[f:") and key.endswith(suffix):
            target = key[5:-len(suffix)]
            if target in self.funcs:
                targets["@cvo." + self.adapters[key][4:]] = self.funcs[target].ll
    kernels: list[str] = []
    for fn in self.fns:
        for b in fn.blocks:
            for i in b.code:
                if i.op != "call" or i.s != lib.ll or len(i.a) != 3:
                    continue
                if [a.t for a in i.a] != ["callable[float,float]", "list[float]", "int"]:
                    continue
                value = i.a[0].v
                if value not in targets or targets[value] not in self.fll:
                    self.out.append("; parallel.map_float: serial in " + fn.f.ll + " (unknown callable)")
                    continue
                target = targets[value]
                reason = kernel_reason(self.fns[self.fll[target]])
                if reason != "":
                    self.out.append("; parallel.map_float: serial " + target + " (" + reason + ")")
                    continue
                self.out.append("; parallel.map_float: native " + target)
                if target not in kernels:
                    kernels.append(target)
                # The typed runtime operation retains both list and count types;
                # its final pointer names only a thunk made from a verified kernel.
                i.op = "rt"
                i.s = self.runtime("pys_parallel_map_f64")
                i.a = [i.a[1], i.a[2], Val("@pys.parallel." + target[1:], "%ptr")]
    return kernels


def parallel_kernel_ir(kernels: list[str]) -> list[str]:
    # The runtime owns the two buffers and proves 0 <= begin <= end <= length.
    # Every output index has exactly one writer. No fast-math, reduction, runtime
    # callback, allocation, exception or GC operation is introduced in workers.
    out: list[str] = []
    for target in kernels:
        out.extend([
            f"define internal void @pys.parallel.{target[1:]}(ptr %src, ptr %dst, i64 %begin, i64 %end) nounwind {{",
            "entry:",
            "  br label %test",
            "test:",
            "  %i = phi i64 [ %begin, %entry ], [ %next, %body ]",
            "  %more = icmp slt i64 %i, %end",
            "  br i1 %more, label %body, label %done",
            "body:",
            "  %in = getelementptr double, ptr %src, i64 %i",
            "  %x = load double, ptr %in, align 8",
            f"  %y = call double {target}(double %x)",
            "  %out = getelementptr double, ptr %dst, i64 %i",
            "  store double %y, ptr %out, align 8",
            "  %next = add i64 %i, 1",
            "  br label %test",
            "done:",
            "  ret void",
            "}",
        ])
    return out
