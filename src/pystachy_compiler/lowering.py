"""Lowering component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val
from src.pystachy_compiler.specs import CHECKED, FXBIT
from src.pystachy_compiler.utils import is_dict, lt, selem, takes_self, targs


def gen_lower(self, fn: IFn) -> None:
    o = self.out
    f = fn.f
    # a method's receiver is never None (callers check it)
    ps = [f"{lt(f.ptypes[j])}{' nonnull' if j == 0 and takes_self(f) else ''} %a{j}" for j in fn.ps]
    o.append(f"define {'' if f.export else 'internal '}{lt(f.ret)} {f.ll}({', '.join(ps)}){' personality ptr @pys_personality' if fn.pads else ''} {{")
    o.append("entry:")
    for i in fn.slots:
        if i.k == 1:
            o.append(f"  %{i.s}.def.{i.r[0]} = alloca i1")
            o.append(f"  store i1 false, ptr %{i.s}.def.{i.r[0]}")
        elif i.k == 2:
            o.append(f"  %stk.{i.r[0]} = alloca [{len(targs(i.t))} x i64], align 8")  # (a tuple: stack_tuple)
        else:
            r = f"%{i.s or 'h'}.{i.r[0]}"
            o.append(f"  {r} = alloca {lt(i.t)}")
            o.append(f"  store {lt(i.t)} zeroinitializer, ptr {r}")
    for b in fn.blocks:
        if b.label != "entry" and b.label != "":
            o.append(b.label + ":")
        for i in b.code:
            self.lower_ins(fn, i)
    o.append("}")

def gen_lower_ins(self, fn: IFn, i: Ins) -> None:
    op = i.op
    o = self.out
    if op == "raw":
        o.append("  " + i.s)
    elif op == "br":
        o.append(f"  br label %{i.b[0]}")
    elif op == "cbr":
        o.append(f"  br i1 {i.a[0].v}, label %{i.b[0]}, label %{i.b[1]}")
    elif op == "check":
        o.append(f"  br i1 {i.a[0].v}, label %{fn.cold[i.x if i.x != '' else i.s]}, label %{i.b[0]}")
    elif op == "phi":
        o.append(f"  %t{i.r[0]} = phi {lt(i.t)} {', '.join([f'[{i.a[j].v}, %{i.b[j]}]' for j in range(len(i.a))])}")
    elif op == "ovf":
        r = i.r
        o.append(f"  %t{r[0]} = call {{i64, i1}} @llvm.{CHECKED[i.s]}.with.overflow.i64(i64 {i.a[0].v}, i64 {i.a[1].v})")
        o.append(f"  %t{r[1]} = extractvalue {{i64, i1}} %t{r[0]}, 0")
        o.append(f"  %t{r[2]} = extractvalue {{i64, i1}} %t{r[0]}, 1")
    elif op == "select":
        x = i.a[1]
        y = i.a[2]
        o.append(f"  %t{i.r[0]} = select i1 {i.a[0].v}, {lt(x.t)} {x.v}, {lt(y.t)} {y.v}")
    elif op == "ret":
        o.append(f"  ret {lt(i.a[0].t)} {i.a[0].v}" if len(i.a) > 0 else "  ret void")
    elif op == "ret.none":
        o.append("  ret void" if fn.f.ret == "None" else "  ret ptr null")
    elif op == "raise":
        o.append(f"  call void @pys_raise(ptr {i.a[0].v}, ptr {i.a[1].v})")
        o.append("  unreachable")
    elif op == "unreachable":
        o.append("  unreachable")
    elif op == "rt":
        f = self.rtfns[i.s]
        ll = f.ll
        vs = [ll[j + 1] + " " + i.a[j].v for j in range(len(i.a))]
        if i.k > 0 and (i.s == "dict.new" or i.s == "set.new"):
            # the key kind of a dict (the element kind of a set) created empty: what its first
            # use showed (0 if nothing did; refine made a tuple key's descriptor a string constant)
            h = self.holes[i.k]
            vs[0] = f"i64 {self.key_kind(targs(h)[0] if is_dict(h) else selem(h)) if h != '' else '0'}"
        c = self.invoke(f"call {ll[0]} @{f.sym}({', '.join(vs)})", i)
        o.append("  " + c if ll[0] == "void" else f"  %t{i.r[0]} = {c}")
    elif op == "call":
        c = self.invoke(f"call {lt(i.t)} {i.s}({', '.join([lt(v.t) + ' ' + v.v for v in i.a])})", i)
        o.append("  " + c if i.t == "None" else f"  %t{i.r[0]} = {c}")
    elif op == "icall":
        # a Callable's code (operand 0), called with its env and the arguments
        c = self.invoke(f"call {lt(i.t)} {i.a[0].v}({', '.join([lt(v.t) + ' ' + v.v for v in i.a[1:]])})", i)
        o.append("  " + c if i.t == "None" else f"  %t{i.r[0]} = {c}")
    elif op == "init":
        o.append("  " + self.invoke(f"call void @init.{i.s}()", i))
    elif op == "list.len":
        o.append(f"  %t{i.r[0]} = load i64, ptr {i.a[0].v}")
    elif op == "list.load":
        # the item of a list at an index within its length (listget): l->a[index], as runtime.c
        # lays a List out ({len, cap, a}), in the 8-byte slot pys_list_get would have returned
        r = i.r
        o.append(f"  %t{r[1]} = getelementptr inbounds {{i64, i64, ptr}}, ptr {i.a[0].v}, i64 0, i32 2")
        o.append(f"  %t{r[2]} = load ptr, ptr %t{r[1]}")
        o.append(f"  %t{r[3]} = getelementptr inbounds i64, ptr %t{r[2]}, i64 {i.a[1].v}")
        o.append(f"  %t{r[0]} = load i64, ptr %t{r[3]}")
    elif op == "landing":
        r = i.r
        o.append(f"  %t{r[0]} = landingpad {{ ptr, i32 }} catch ptr null")
        o.append(f"  %t{r[1]} = extractvalue {{ ptr, i32 }} %t{r[0]}, 0")
        o.append(f"  store ptr %t{r[1]}, ptr {i.a[0].v}")
        o.append(f"  br label %{i.b[0]}")
    elif op == "throw":
        o.append(f"  call void @pys_throw(ptr {i.a[0].v})")
        o.append("  unreachable")
    elif op == "exc.match":
        o.append(f"  %t{i.r[0]} = call i64 @pys_exc_in(ptr {i.a[0].v}, ptr {i.a[1].v})")
        o.append(f"  %t{i.r[1]} = icmp ne i64 %t{i.r[0]}, 0")
    else:
        fail(f"internal error: no lowering for IR op {op}", 0)

def gen_invoke(self, c: str, i: Ins) -> str:
    # the call c of op i, an invoke if the exception passes made it one (Ins.b: [next, landing])
    return c if len(i.b) == 0 else f"invoke{c[4:]} to label %{i.b[0]} unwind label %{i.b[1]}"

# ---- the IR's check (PYSTACHY_IRCHECK=1) and its effect summaries, once the program is built
def gen_eh_ir(self, fn: IFn) -> None:
    # fn has try statements: its blocks' exception edges (Blk.handler) become LLVM's, once the
    # effect summaries say which calls may raise. A raise or throw that a landing block covers
    # branches to the code after it, with the exception in its try's slot as the landing op
    # stores it: no unwinder, which takes a microsecond. (A raise's exception is made as
    # pys_raise makes it, from its kind and message: in a program that has try or with, no raise op
    # has the line of a SyntaxError as its kind, see raise_stmt.) A call a landing block covers
    # that may raise (R) becomes an invoke whose unwind edge goes there, and ends its block (a
    # phi after it names the last part as its predecessor). A landing block no invoke goes to
    # is dropped (the code after it may still be reached from a raise), and a function left
    # without one has no personality
    lands: dict[str, Ins] = {}
    for b in fn.blocks:
        if len(b.code) > 0 and b.code[0].op == "landing":
            lands[b.label] = b.code[0]
    used: dict[str, bool] = {}
    ren: dict[str, str] = {}
    blocks: list[Blk] = []
    raises = FXBIT["R"]
    for b in fn.blocks:
        if b.handler == "":
            blocks.append(b)
            continue
        code = b.code
        t = code[-1]
        if t.op == "raise" or t.op == "throw":
            lp = lands[b.handler]
            code = code[: len(code) - 1]
            ex = t.a[0].v
            if t.op == "raise":
                fn.n += 1
                i = Ins("rt", "exc", "exc.new")
                i.a = [t.a[0], t.a[1], Val("null", "str")]
                i.r = [fn.n]
                self.runtime("pys_exc_new")
                code.append(i)
                ex = f"%t{fn.n}"
            code.append(Ins("raw", "", f"store ptr {ex}, ptr {lp.a[0].v}"))
            br = Ins("br", "", "")
            br.b = [lp.b[0]]
            code.append(br)
        cur = b
        cur.code = []
        for j in range(len(code)):
            i = code[j]
            cur.code.append(i)
            if j < len(code) - 1 and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init") and self.opfx(i, fn.fa) & raises != 0:
                fn.n += 1
                i.b = [f"L{fn.n}", b.handler]
                used[b.handler] = True
                blocks.append(cur)
                cur = Blk(i.b[0])
                cur.handler = b.handler
        blocks.append(cur)
        if cur is not b:
            ren[b.label] = cur.label
    fn.blocks = []
    for b in blocks:
        if b.label in lands and b.label not in used:
            continue
        fn.blocks.append(b)
        for i in b.code:
            if i.op != "phi":
                break
            for j in range(len(i.b)):
                if i.b[j] in ren:
                    i.b[j] = ren[i.b[j]]
    fn.pads = len(used) > 0
    if fn.pads:
        self.runtime("pys_personality")
