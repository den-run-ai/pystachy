"""Lowering component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val
from src.pystachy_compiler.lower_module import struct_types
from src.pystachy_compiler.specs import CHECKED, FCMP, FXBIT, GENDONE, GENNAME, GENNEW, GENRET, GENSLOTS, GENSLOTSX, GENSTATE, ICMP, RANGEC, STRLEN_RANGE, TBAA_BYTES, TBAA_FIELDS, TBAA_LEN, TBAA_SIZES
from src.pystachy_compiler.utils import atomic_dict, atomic_list, is_dict, is_tuple, lt, selem, takes_self, targs


def gen_lower(self, fn: IFn) -> None:
    o = self.out
    f = fn.f
    # a method's receiver is never None (callers check it)
    ps = [f"{lt(f.ptypes[j])}{' nonnull' if j == 0 and takes_self(f) else ''} %a{j}" for j in fn.ps]
    # tupleret: a function that returns its tuple's slots by value (Gen.tuple_rets) is lowered as
    # @v.<its symbol>, returning them as an LLVM aggregate, and its own symbol is a wrapper below
    n = self.vrets.get(f.ll, 0)
    agg = "{" + ", ".join(["i64" for _ in range(n)]) + "}"
    self.vtuples = fresh_rets(fn) if n > 0 else {}
    self.vslots = {}
    self.vaggs = {}
    # (a generator function is a coroutine that LLVM's coroutine passes split: see gen.start)
    # (a function that only raises is an error path: cold, and kept out of its callers, so that
    # what it formats does not keep LLVM from inlining the checks that call it: raises_only)
    o.append(f"define {'' if f.export else 'internal '}{agg if n > 0 else lt(f.ret)} {'@v.' + f.ll[1:] if n > 0 else f.ll}({', '.join(ps)}){' presplitcoroutine' if fn.coro else ''}{' cold noinline' if raises_only(fn) else ''}{' personality ptr @pys_personality' if fn.pads else ''} {{")
    o.append("entry:")
    self.ftags = {}  # (its own numbers: another function's %tN is no field address of this one)
    if fn.coro:
        o.append(f"  %coro.promise = alloca [{GENSLOTSX if self.gproto else GENSLOTS} x i64], align 8")
        self.coros = True
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
        self.lowblk = b.label
        for i in b.code:
            self.lower_ins(fn, i)
    if fn.coro:
        # where a generator's suspends go when it is destroyed (coro.free: nothing to free, the
        # collector reclaims the frame) and when it suspends (its caller or resumer goes on)
        o.append("coro.final:")  # (resuming a generator there is never done: coro.unreach)
        o.append("  %coro.last = call i8 @llvm.coro.suspend(token none, i1 true)")
        o.append("  switch i8 %coro.last, label %coro.ret [i8 0, label %coro.unreach i8 1, label %coro.cleanup]")
        o.append("coro.cleanup:")
        o.append("  %coro.free = call ptr @llvm.coro.free(token %coro.id, ptr %coro.hdl)")
        o.append("  br label %coro.ret")
        o.append("coro.ret:")
        o.append("  %coro.end = call i1 @llvm.coro.end(ptr %coro.hdl, i1 false, token none)")
        o.append("  ret ptr %coro.hdl")
        o.append("coro.unreach:")
        o.append("  unreachable")
    o.append("}")
    if n > 0:
        # its symbol, for every other use: the tuple, made from the slots the body returns
        o.append(f"define internal ptr {f.ll}({', '.join(ps)}) {{")
        o.append("entry:")
        o.append(f"  %v = call {agg} @v.{f.ll[1:]}({', '.join([f'{lt(f.ptypes[j])} %a{j}' for j in fn.ps])})")
        o.append(f"  %p = call ptr @{self.rtfns['alloc'].sym}(i64 {8 * n})")
        for k in range(n):
            o.append(f"  %v{k} = extractvalue {agg} %v, {k}")
            o.append(f"  %p{k} = getelementptr i64, ptr %p, i64 {k}")
            o.append(f"  store i64 %v{k}, ptr %p{k}")
        o.append("  ret ptr %p")
        o.append("}")

def gen_tuple_rets(self) -> None:
    # tupleret: which functions return their fixed tuple's slots by value, and which calls take
    # them so (Gen.vrets, Gen.vcalls), once the program's IR is final. Such a function returns,
    # wherever it returns, a tuple that an alloc.fixed of the ret's block made, which nothing but
    # that block's tuple.stores reach (fresh_rets): a new tuple, which no code could hold. Such
    # a call's result is read by tuple.loads alone (an unpacking, a constant index, a loop over
    # the tuple's slots): the tuple could not escape it either, so CPython's identity of it is
    # never seen. A function that such a call calls is lowered to return the slots (gen_lower);
    # the others are lowered as before
    fns: dict[str, int] = {}
    for fn in self.fns:
        if len(fresh_rets(fn)) > 0:
            fns[fn.f.ll] = len(targs(fn.f.ret))
    for fn in self.fns:
        calls: dict[str, str] = {}
        used: dict[str, bool] = {}  # (values that an op reads other than as a tuple.load's tuple)
        for b in fn.blocks:
            for i in b.code:
                if i.op == "call" and i.s in fns and len(i.r) == 1:
                    calls[f"%t{i.r[0]}"] = i.s
                for j in range(len(i.a)):
                    if i.op != "tuple.load" or j != 0:
                        used[i.a[j].v] = True
        for v in calls:
            if v not in used:
                self.vcalls[f"{fn.f.ll} {v}"] = True
                self.vrets[calls[v]] = fns[calls[v]]

def fresh_rets(fn: IFn) -> dict[str, bool]:
    # the tuples that fn returns (tupleret), if each is made by an alloc.fixed of its ret's block,
    # of fn's fixed tuple type, and nothing but tuple.stores and the ret reach it; else none. Not a
    # generator's (its returns are gen.ret), nor an exported function's, whose ABI C or CPython use
    t = fn.f.ret
    if fn.coro or fn.f.export or fn.f.pyexport or not is_tuple(t) or not t.endswith("]") or len(targs(t)) == 0 or "..." in targs(t) or "" in targs(t):
        return {}
    rets: dict[str, bool] = {}
    for b in fn.blocks:
        made: dict[str, bool] = {}
        for i in b.code:
            if i.op == "alloc.fixed" and i.t == t:
                made[f"%t{i.r[0]}"] = True
            elif i.op == "ret.none" or (i.op == "ret" and (len(i.a) != 1 or i.a[0].v not in made)):
                return {}
            elif i.op == "ret":
                rets[i.a[0].v] = True
    for b in fn.blocks:
        for i in b.code:
            for j in range(len(i.a)):
                if i.a[j].v in rets and i.op != "ret" and (i.op != "tuple.store" or j != 0):
                    return {}
    return rets

def raises_only(fn: IFn) -> bool:
    # whether no call of fn returns: it has no ret, and no branch back to a block before it (a
    # loop, which might run until the program ends), so that every path raises or exits. Not a
    # generator, nor a module's code, which runs once even where it ends raising (sys.exit())
    if fn.coro or fn.f.name == "<module>":
        return False
    at: dict[str, int] = {}
    for j in range(len(fn.blocks)):
        at[fn.blocks[j].label] = j
    for j in range(len(fn.blocks)):
        for i in fn.blocks[j].code:
            if i.op == "ret" or i.op == "ret.none":
                return False
            for lb in i.b:
                if lb in at and at[lb] <= j:
                    return False
    return True

def gen_field_tag(self, c: str, k: int) -> str:
    # the TBAA of the loads and stores of field k of an object of class c (fieldtbaa): ", !tbaa !N"
    # with the number of its access tag (from TBAA_FIELDS, as first asked for: lower_module prints
    # them, Gen.tbaa_nodes), or "" where c's layout has a member of no known size. A derived
    # class's struct begins with its base's, flags included (fl_fields): a field there is tagged
    # as its base's, so that an access through either class has the same tag, and LLVM's
    # struct-path TBAA tells apart only the fields of one class at different offsets and those
    # of classes neither of which lays out the other's (Gen.disjoint's rule). The tags have a
    # root of their own: no access of runtime.c's or of runtime.py's is told apart from them
    ci = self.classes[c]
    while ci.base in self.classes and k < len(self.classes[ci.base].fields) + self.classes[ci.base].nflag:
        ci = self.classes[ci.base]
    key = f"{ci.name} {k}"
    if key not in self.tbaa:
        if len([t for t in struct_types(ci) if t not in TBAA_SIZES]) > 0:
            return ""
        self.tbaa[key] = TBAA_FIELDS + len(self.tbaa)
    return f", !tbaa !{self.tbaa[key]}"

def gen_lower_ins(self, fn: IFn, i: Ins) -> None:
    op = i.op
    o = self.out
    if op == "scalar.bin" or op == "scalar.cast" or op == "scalar.cmp":
        self.lower_scalar(i)

    elif op == "mach.load" or op == "mach.store":
        metadata = f", !tbaa !{TBAA_LEN}" if i.s == "length" or i.s == "length.range" else f", !tbaa !{TBAA_BYTES}" if i.s == "bytes" else ""
        if i.s == "length.range":
            metadata += f", !range !{STRLEN_RANGE}"
        if op == "mach.load":
            o.append(f"  %t{i.r[0]} = load {lt(i.t)}, ptr {i.a[0].v}{metadata}")
        else:
            o.append(f"  store {lt(i.a[1].t)} {i.a[1].v}, ptr {i.a[0].v}{metadata}")
    elif op == "mach.addr":
        o.append(f"  %t{i.r[0]} = getelementptr{' inbounds' if i.k == 1 else ''} {lt(i.s)}, ptr {i.a[0].v}, i64 {i.a[1].v}")
    elif op == "mem.load":
        o.append(f"  %t{i.r[0]} = load {'ptr' if i.t == 'None' else lt(i.t)}, ptr {i.a[0].v}{self.ftags.get(i.a[0].v, '')}")
    elif op == "mem.store":
        v = i.a[1]
        o.append(f"  store {'ptr' if v.t == 'None' else lt(v.t)} {v.v}, ptr {i.a[0].v}{self.ftags.get(i.a[0].v, '')}")
    elif op == "field.addr":
        self.rangeused = self.rangeused or i.a[0].t == RANGEC
        o.append(f"  %t{i.r[0]} = getelementptr %C.{i.a[0].t}, ptr {i.a[0].v}, i32 0, i32 {i.k}")
        if "fieldtbaa" in self.opts:
            self.ftags[f"%t{i.r[0]}"] = self.field_tag(i.a[0].t, i.k)
    elif op == "alloc.fixed":
        self.rangeused = self.rangeused or i.t == RANGEC
        size = str(8 * len(targs(i.t))) if is_tuple(i.t) else f"ptrtoint (ptr getelementptr (%C.{i.t}, ptr null, i32 1) to i64)"
        if f"%t{i.r[0]}" not in self.vtuples:  # (a tuple returned by value is never made: tupleret)
            o.append(f"  %t{i.r[0]} = call ptr @{self.rtfns['alloc'].sym}(i64 {size})")
    elif op == "tuple.store" and i.a[0].v in self.vtuples:
        self.vslots[f"{i.a[0].v} {i.k}"] = i.a[1].v  # (the slot its ret returns)
    elif op == "tuple.load" and i.a[0].v in self.vaggs:
        o.append(f"  %t{i.r[1]} = extractvalue {self.vaggs[i.a[0].v]} {i.a[0].v}, {i.k}")
    elif op == "tuple.load" or op == "tuple.store":
        o.append(f"  %t{i.r[0]} = getelementptr i64, ptr {i.a[0].v}, i64 {i.k}")
        if op == "tuple.load":
            o.append(f"  %t{i.r[1]} = load i64, ptr %t{i.r[0]}")
        else:
            o.append(f"  store i64 {i.a[1].v}, ptr %t{i.r[0]}")
    elif op == "slot.pack":
        v = i.a[0]
        c = f"bitcast double {v.v} to i64" if v.t == "float" else f"zext i1 {v.v} to i64" if v.t == "bool" else f"bitcast i64 {v.v} to i64" if v.t == "int" else f"ptrtoint ptr {v.v} to i64"
        o.append(f"  %t{i.r[0]} = {c}")
    elif op == "slot.unpack":
        v = i.a[0]
        c = f"bitcast i64 {v.v} to double" if i.t == "float" else f"trunc i64 {v.v} to i1" if i.t == "bool" else f"bitcast i64 {v.v} to i64" if i.t == "int" else f"inttoptr i64 {v.v} to ptr"
        o.append(f"  %t{i.r[0]} = {c}")
    elif op == "union.tag":
        o.append(f"  %t{i.r[0]} = load i64, ptr {i.a[0].v}")
    elif op == "num.cast":
        v = i.a[0]
        c = f"zext i1 {v.v} to i64" if i.t == "int" else f"uitofp i1 {v.v} to double" if v.t == "bool" else f"sitofp i64 {v.v} to double"
        o.append(f"  %t{i.r[0]} = {c}")
    elif op == "num.cmp":
        v = i.a[0]
        c = f"icmp {ICMP[i.s]} i64" if v.t == "int" else f"fcmp {FCMP[i.s]} double"
        o.append(f"  %t{i.r[0]} = {c} {v.v}, {i.a[1].v}")
    elif op == "int.ucmp":
        o.append(f"  %t{i.r[0]} = icmp u{ICMP[i.s][1:]} i64 {i.a[0].v}, {i.a[1].v}")
    elif op == "ptr.cmp":
        o.append(f"  %t{i.r[0]} = icmp {ICMP[i.s]} ptr {i.a[0].v}, {i.a[1].v}")
    elif op == "union.payload":
        o.append(f"  %t{i.r[0]} = getelementptr i64, ptr {i.a[0].v}, i64 1")
        o.append(f"  %t{i.r[1]} = load i64, ptr %t{i.r[0]}")
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
    elif op == "ret" and len(i.a) > 0 and i.a[0].v in self.vtuples:
        # the tuple's slots, by value (tupleret): what its tuple.stores gave each, else the zero
        # of the tuple that alloc.fixed would have made
        n = len(targs(fn.f.ret))
        agg = "{" + ", ".join(["i64" for _ in range(n)]) + "}"
        cur = "zeroinitializer"
        for k in range(n):
            s = self.vslots.get(i.a[0].v + " " + str(k), "0")
            o.append(f"  {i.a[0].v}.v{k} = insertvalue {agg} {cur}, i64 {s}, {k}")
            cur = f"{i.a[0].v}.v{k}"
        o.append(f"  ret {agg} {cur}")
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
        if i.k > 0 and ((i.s == "list.new" and atomic_list(self.holes[i.k])) or (i.s == "dict.new" and atomic_dict(self.holes[i.k]))):
            # a list or dict created empty whose type a later use decided: of int, float or bool
            # items (values), which no other type can reach (an open hole is not one of these)
            f = self.rtfns[self.runtime("pys_list_new_atomic" if i.s == "list.new" else "pys_dict_new_atomic")]
        ll = f.ll
        vs = [ll[j + 1] + " " + i.a[j].v for j in range(len(i.a))]
        if i.k > 0 and (i.s == "dict.new" or i.s == "set.new"):
            # the key kind of a dict (the element kind of a set) created empty: what its first
            # use showed (0 if nothing did; refine made a tuple key's descriptor a string constant)
            h = self.holes[i.k]
            vs[0] = f"i64 {self.key_kind(targs(h)[0] if is_dict(h) else selem(h)) if h != '' else '0'}"
        c = self.invoke(f"call {ll[0]} @{f.sym}({', '.join(vs)})", i)
        o.append("  " + c if ll[0] == "void" else f"  %t{i.r[0]} = {c}")
    elif op == "call" and len(i.r) == 1 and f"{fn.f.ll} %t{i.r[0]}" in self.vcalls:
        # the slots of the tuple a function returns, by value, to tuple.loads alone (tupleret)
        agg = "{" + ", ".join(["i64" for _ in range(self.vrets[i.s])]) + "}"
        args = ", ".join([lt(v.t) + " " + v.v for v in i.a])
        o.append(f"  %t{i.r[0]} = {self.invoke(f'call {agg} @v.{i.s[1:]}({args})', i)}")
        self.vaggs[f"%t{i.r[0]}"] = agg
    elif op == "call":
        c = self.invoke(f"call {lt(i.t)} {i.s}({', '.join([lt(v.t) + ' ' + v.v for v in i.a])})", i)
        o.append("  " + c if i.t == "None" else f"  %t{i.r[0]} = {c}")
    elif op == "icall":
        # a Callable's code (operand 0), called with its env and the arguments
        c = self.invoke(f"call {lt(i.t)} {i.a[0].v}({', '.join([lt(v.t) + ' ' + v.v for v in i.a[1:]])})", i)
        o.append("  " + c if i.t == "None" else f"  %t{i.r[0]} = {c}")
    elif op == "init":
        o.append("  " + self.invoke(f"call void @init.{i.s}()", i))
    elif op == "empty.kind":
        # Only fresh empty results may change their dict/set key layout. A later
        # return can resolve the hole; an outer caller types an unresolved result.
        t = self.holes[i.k] if i.k > 0 else i.a[0].t
        kind = self.key_kind(targs(t)[0] if is_dict(t) else selem(t)) if t != "" else "0"
        o.append(f"  %t{i.r[0]} = getelementptr i64, ptr {i.a[0].v}, i64 1")
        o.append(f"  store i64 {kind}, ptr %t{i.r[0]}")
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
    elif op == "gen.start":
        # a switched-resume coroutine: its frame (coro.size bytes, from pys_alloc unless
        # CoroElide puts it in its caller's frame: coro.alloc false) and promise, zeroed but for
        # its name; then the initial suspend, so that a call runs none of the generator's body
        o.append("  %coro.id = call token @llvm.coro.id(i32 8, ptr %coro.promise, ptr null, ptr null)")
        o.append("  %coro.need = call i1 @llvm.coro.alloc(token %coro.id)")
        o.append("  br i1 %coro.need, label %coro.alloc, label %coro.begin")
        o.append("coro.alloc:")
        o.append("  %coro.size = call i64 @llvm.coro.size.i64()")
        o.append(f"  %coro.mem = call ptr @{self.rtfns['alloc'].sym}(i64 %coro.size)")
        o.append("  br label %coro.begin")
        o.append("coro.begin:")
        o.append(f"  %coro.frame = phi ptr [null, %{self.lowblk}], [%coro.mem, %coro.alloc]")
        o.append("  %coro.hdl = call ptr @llvm.coro.begin(token %coro.id, ptr %coro.frame)")
        o.append(f"  store [{GENSLOTSX if self.gproto else GENSLOTS} x i64] zeroinitializer, ptr %coro.promise")
        o.append(f"  %coro.name = getelementptr i64, ptr %coro.promise, i64 {GENNAME}")
        o.append(f"  store ptr {i.a[0].v}, ptr %coro.name")
        if self.gproto:
            # (not started: what send() and throw() tell from a generator suspended at a yield)
            o.append(f"  %coro.new = getelementptr i64, ptr %coro.promise, i64 {GENSTATE}")
            o.append(f"  store i64 {GENNEW}, ptr %coro.new")
        o.append("  %coro.first = call i8 @llvm.coro.suspend(token none, i1 false)")
        o.append(f"  switch i8 %coro.first, label %coro.ret [i8 0, label %{i.b[0]} i8 1, label %coro.cleanup]")
    elif op == "gen.yield":
        # the value in the promise, the state (k: whether closing it here runs code of its), suspend
        o.append(f"  store i64 {i.a[0].v}, ptr %coro.promise")
        o.append(f"  %t{i.r[0]} = getelementptr i64, ptr %coro.promise, i64 {GENSTATE}")
        o.append(f"  store i64 {i.k}, ptr %t{i.r[0]}")
        o.append(f"  %t{i.r[1]} = call i8 @llvm.coro.suspend(token none, i1 false)")
        o.append(f"  switch i8 %t{i.r[1]}, label %coro.ret [i8 0, label %{i.b[0]} i8 1, label %coro.cleanup]")
    elif op == "gen.ret":
        # the value returned, finished; then the final suspend, which LLVM requires to be one
        o.append(f"  %t{i.r[0]} = getelementptr i64, ptr %coro.promise, i64 {GENRET}")
        if len(i.a) > 0:
            o.append(f"  store i64 {i.a[0].v}, ptr %t{i.r[0]}")
        o.append(f"  %t{i.r[1]} = getelementptr i64, ptr %coro.promise, i64 {GENSTATE}")
        o.append(f"  store i64 {GENDONE}, ptr %t{i.r[1]}")
        o.append("  br label %coro.final")
    elif op == "gen.promise":
        if len(i.a) == 0:
            o.append(f"  %t{i.r[0]} = getelementptr i64, ptr %coro.promise, i64 0")
        else:
            o.append(f"  %t{i.r[0]} = call ptr @llvm.coro.promise(ptr {i.a[0].v}, i32 8, i1 false)")
    elif op == "gen.resume":
        o.append("  " + self.invoke(f"call void @llvm.coro.resume(ptr {i.a[0].v})", i))
    elif op == "gen.drop":
        o.append(f"  call void @pys.gen.drop(ptr {i.a[0].v})")
        self.gendrops = True
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
            st = Ins("mach.store", "", "")
            st.a = [Val(lp.a[0].v, "%ptr"), Val(ex, "%ptr")]
            code.append(st)
            br = Ins("br", "", "")
            br.b = [lp.b[0]]
            code.append(br)
        cur = b
        cur.code = []
        for j in range(len(code)):
            i = code[j]
            cur.code.append(i)
            if j < len(code) - 1 and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init" or i.op == "gen.resume") and self.opfx(i, fn.fa) & raises != 0:
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


def gen_lower_scalar(self, i: Ins) -> None:
    a = i.a[0]
    if i.op == "scalar.bin":
        s = i.s + (" " + i.x if i.x != "" else "") + " " + lt(a.t) + " " + a.v
        if len(i.a) == 2:
            s += ", " + i.a[1].v
    elif i.op == "scalar.cast":
        s = i.s + " " + lt(a.t) + " " + a.v + " to " + lt(i.t)
    else:
        s = ("fcmp" if a.t == "float" else "icmp") + " " + i.s + " " + lt(a.t) + " " + a.v + ", " + i.a[1].v
    self.out.append(f"  %t{i.r[0]} = {s}")

