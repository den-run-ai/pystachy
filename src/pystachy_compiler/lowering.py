"""Lowering component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail, int_program
from src.pystachy_compiler.ir import Blk, ClassInfo, IFn, Ins, Val, slot_register, tmpname, one_num
from src.pystachy_compiler.lower_module import const_slot, struct_types
from src.pystachy_compiler.specs import CHECKED, FCMP, FXBIT, GENDONE, GENNAME, GENNEW, GENRET, GENRETP, GENSLOTS, GENSLOTSB, GENSLOTSX, GENSTATE, GENVALP, ICMP, LISTLEN_RANGE, OBJECTC, RANGEC, STRLEN_RANGE, TBAA_BYTES, TBAA_DEPTH, TBAA_FIELDS, TBAA_LEN, TBAA_SIZES
from src.pystachy_compiler.utils import atomic_dict, atomic_list, identity_abi, numeric_identity, is_dict, is_tuple, lt, selem, takes_self, targs, tslots


def gen_lower(self, fn: IFn) -> None:
    o = self.out
    chunk_start = len(o)
    f = fn.f
    # Attribute calls check receivers; explicit class calls may pass None as self.
    ps = [f"{lt(f.ptypes[j])}{' nonnull' if j == 0 and takes_self(f) and not f.nullable_self else ''} %a{j}" for j in fn.ps]
    if identity_abi(f):
        ps.extend([f"ptr %aid{j}" for j in fn.ps if numeric_identity(f.ptypes[j])])
        if numeric_identity(f.ret):
            ps.append("ptr %idret")
    # tupleret: a function that returns its tuple's slots by value (Gen.tuple_rets) is lowered as
    # @v.<its symbol>, returning them as an LLVM aggregate, and its own symbol is a wrapper below
    n = self.vrets.get(f.ll, 0)
    agg = vagg(n, f.ll in self.vconst)
    self.vtuples = fresh_rets(fn) if n > 0 else {}
    self.vslots = {}
    self.vaggs = {}
    # closed recursion (Gen.recursionscope): the body is @r.<its symbol>, whose last argument is
    # the depth its caller was at (%rd), and its own symbol is a wrapper below
    rd = f.ll in self.rdpass
    cold = " cold noinline" if raises_only(fn) else ""
    name = "@v." + f.ll[1:] if n > 0 else "@r." + f.ll[1:] if rd else f.ll
    scope = self.source_lines.function(f.name, name, f.node.line)
    debug = " !dbg " + scope if scope != "" else ""
    # (a generator function is a coroutine that LLVM's coroutine passes split: see gen.start)
    # (a function that only raises is an error path: cold, and kept out of its callers, so that
    # what it formats does not keep LLVM from inlining the checks that call it: raises_only)
    o.append(f"define {'' if f.export and not rd else 'internal '}{agg if n > 0 else lt(f.ret)} {name}({', '.join(ps + ['i64 %rd'] if rd else ps)}){' presplitcoroutine' if fn.coro else ''}{cold}{' personality ptr @pys_personality' if fn.pads else ''}{debug} {{")
    o.append("entry:")
    prologue = len(o)
    self.ftags = {}  # (its own numbers: another function's %tN is no field address of this one)
    if fn.coro:
        o.append(f"  %coro.promise = alloca [{promise_slots(self.gproto)} x i64], align 8")
        self.coros = True
    for i in fn.slots:
        r = slot_register(i)
        if i.k == 1:
            o.append(f"  {r} = alloca i1")
            o.append(f"  store i1 false, ptr {r}")
        elif i.k == 2:
            o.append(f"  {r} = alloca [{tslots(i.t)} x i64], align 8")  # (a tuple: stack_tuple)
        else:
            o.append(f"  {r} = alloca {lt(i.t)}")
            o.append(f"  store {lt(i.t)} zeroinitializer, ptr {r}")
    self.source_lines.mark(o, prologue, scope, 0)
    for b in fn.blocks:
        if b.label != "entry" and b.label != "":
            o.append(b.label + ":")
        self.lowblk = b.label
        for i in b.code:
            instruction_start = len(o)
            self.lower_ins(fn, i)
            self.source_lines.mark(o, instruction_start, scope, i.line)
    epilogue = len(o)
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
        # coro.end's older two-argument form, its result unnamed: LLVM 18 to 23 upgrade it as they
        # read it to their own (ptr, i1, token), which returns i1 up to LLVM 21 and void from 22
        # (which rejects the three-argument form returning i1). Only an LLVM 22 or 23 built with
        # assertions would stop at that upgrade, where the result's type changes; LLVM's main
        # branch upgrades either form explicitly
        o.append("  call i1 @llvm.coro.end(ptr %coro.hdl, i1 false)")
        o.append("  ret ptr %coro.hdl")
        o.append("coro.unreach:")
        o.append("  unreachable")
    self.source_lines.mark(o, epilogue, scope, 0)
    o.append("}")
    if rd:
        # its symbol, for every caller outside its cycle (and as a value): the body at the depth
        # word's value, which the cycle leaves as it found it. It stays out of line (a load and a
        # jump to the body): inlined, it adds a load and an argument to every caller, which can
        # cost them their own inlining (clang kept the regex search's Pattern._search out of
        # re.search; see the historical report linked from docs/internals.md#native-recursion-depth).
        o.append(f"define {'' if f.export else 'internal '}{lt(f.ret)} {f.ll}({', '.join(ps)}){cold or ' noinline'} {{")
        o.append("entry:")
        forwarded = [f'{lt(f.ptypes[j])} %a{j}' for j in fn.ps]
        if identity_abi(f):
            forwarded.extend([f"ptr %aid{j}" for j in fn.ps if numeric_identity(f.ptypes[j])])
            if numeric_identity(f.ret):
                forwarded.append("ptr %idret")
        forwarded.append("i64 %rd")
        o.append(f"  %rd = load i64, ptr @pys_recursion_state, !tbaa !{TBAA_DEPTH}")
        if lt(f.ret) == "void":
            o.append(f"  call void @r.{f.ll[1:]}({', '.join(forwarded)})")
            o.append("  ret void")
        else:
            o.append(f"  %r = call {lt(f.ret)} @r.{f.ll[1:]}({', '.join(forwarded)})")
            o.append(f"  ret {lt(f.ret)} %r")
        o.append("}")
    if n > 0:
        # its symbol, for every other use: the tuple, made from the slots the body returns
        o.append(f"define internal ptr {f.ll}({', '.join(ps)}) {{")
        o.append("entry:")
        forwarded = [f'{lt(f.ptypes[j])} %a{j}' for j in fn.ps]
        if identity_abi(f):
            forwarded.extend([f"ptr %aid{j}" for j in fn.ps if numeric_identity(f.ptypes[j])])
            if numeric_identity(f.ret):
                forwarded.append("ptr %idret")
        o.append(f"  %v = call {agg} @v.{f.ll[1:]}({', '.join(forwarded)})")
        if f.ll in self.vconst:
            # (where the body returned a constant tuple, that tuple: Gen.tuple_const)
            o.append(f"  %c = extractvalue {agg} %v, {n}")
            o.append("  %k = icmp ne ptr %c, null")
            o.append("  br i1 %k, label %const, label %made")
            o.append("const:")
            o.append("  ret ptr %c")
            o.append("made:")
        o.append(f"  %p = {self.alloc_call(str(8 * n), f.ret)}")
        for k in range(n):
            o.append(f"  %v{k} = extractvalue {agg} %v, {k}")
            o.append(f"  %p{k} = getelementptr i64, ptr %p, i64 {k}")
            o.append(f"  store i64 %v{k}, ptr %p{k}")
        o.append("  ret ptr %p")
        o.append("}")
    # Only module assembly reads completed output: keep this function and its wrappers as
    # one chunk, releasing the individual line strings before lowering the next function.
    text = "\n".join(o[chunk_start:])
    del o[chunk_start:]
    o.append(text)

def gen_alloc_call(self, size: str, t: str) -> str:
    # the call that gives compiled code size zeroed bytes for an object or a fixed tuple of type t
    # (alloc.fixed, a tupleret wrapper's tuple), which declares the runtime function it calls.
    # With allocelide, an object that holds no reference (ref_free) comes from pys_new, a call
    # that the program marks as an allocation, which LLVM may delete when nothing keeps its
    # object (it sees each call: runtime.c keeps pys_new out of line; an AOT build then inlines
    # the allocator's fast path into the calls left, driver.py). Every other object comes from
    # pys_alloc, as without allocelide: the marked call's object is noalias, so LLVM forwards
    # its fields' loads across calls, and then deletes the object or leaves its address dead
    # while the program still reads it, after which the conservative collector finds nothing
    # that the object holds (a referent of a weak reference, a file, an ffi.track reference)
    # while it is in use. An object that holds no reference keeps nothing alive: deleting it
    # changes no other object's lifetime. The runtime's own code (rtmode) calls pys_alloc
    if "allocelide" in self.opts and not self.rtmode and ref_free(self.classes, t):
        return f'call noalias nonnull ptr @{self.rtfns[self.runtime("pys_new")].sym}(i64 {size}) allockind("alloc,zeroed") allocsize(0) "alloc-family"="pys"'
    return f"call ptr @{self.rtfns[self.runtime('pys_alloc')].sym}(i64 {size})"

def ref_free(classes: dict[str, ClassInfo], t: str) -> bool:
    # does every word of an object or fixed tuple of type t hold a 64-bit int, a float or a bool,
    # so that it holds no reference, by the compiler's types: a tuple's items, a class's fields,
    # its bases' and the hidden ones among them (a hierarchy's class word, the base's "is
    # assigned" flags, which are bools, and its numeric identity companions, which are boxes),
    # then its own flags and companions (struct_types). Not by its LLVM types: a pointer item of a
    # tuple is an i64 slot, and so is a promoting int item's Mpz word (tslots)
    if is_tuple(t):
        return all(x in ["int", "float", "bool"] for x in targs(t))
    if t not in classes:
        return False
    ci = classes[t]
    return ci.nbox == 0 and all(ci.ftypes[x] in ["int", "float", "bool"] for x in ci.fields)

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
        # (one that returns constant tuples alone returns their addresses, which need no tuple made)
        rets = fresh_rets(fn)
        if len([v for v in rets if not v.startswith("@tc.")]) > 0:
            fns[fn.f.ll] = tslots(fn.f.ret)
            if len([v for v in rets if v.startswith("@tc.")]) > 0:
                self.vconst[fn.f.ll] = True  # (its slots go with the constant's address: vagg)
    for fn in self.fns:
        calls: dict[str, str] = {}
        used: dict[str, bool] = {}  # (values that an op reads other than as a tuple.load's tuple)
        for b in fn.blocks:
            for i in b.code:
                if i.op == "call" and i.s in fns and len(i.r) == 1:
                    calls[tmpname(i.r[0])] = i.s
                for j in range(len(i.a)):
                    if i.op != "tuple.load" or j != 0:
                        used[i.a[j].v] = True
        for v in calls:
            if v not in used:
                self.vcalls[f"{fn.f.ll} {v}"] = True
                self.vrets[calls[v]] = fns[calls[v]]

def fresh_rets(fn: IFn) -> dict[str, bool]:
    # the tuples that fn returns (tupleret), if each is made by an alloc.fixed of its ret's block,
    # of fn's fixed tuple type, and nothing but tuple.stores and the ret reach it, or is a constant
    # tuple of that type (@tc.N, which any code may read: Gen.tuple_const); else none. Not a
    # generator's (its returns are gen.ret), nor an exported function's, whose ABI C or CPython use
    t = fn.f.ret
    if fn.coro or fn.f.export or fn.f.pyexport or not is_tuple(t) or not t.endswith("]") or len(targs(t)) == 0 or "..." in targs(t) or "" in targs(t):
        return {}
    rets: dict[str, bool] = {}
    for b in fn.blocks:
        made: dict[str, bool] = {}
        for i in b.code:
            if i.op == "alloc.fixed" and i.t == t:
                made[tmpname(i.r[0])] = True
            elif i.op == "ret.none" or (i.op == "ret" and (len(i.a) != 1 or (i.a[0].v not in made and not (i.a[0].v.startswith("@tc.") and i.a[0].t == t)))):
                return {}
            elif i.op == "ret":
                rets[i.a[0].v] = True
    for b in fn.blocks:
        for i in b.code:
            for j in range(len(i.a)):
                if i.a[j].v in rets and not i.a[j].v.startswith("@tc.") and i.op != "ret" and (i.op != "tuple.store" or j != 0):
                    return {}
    return rets


def vagg(n: int, c: bool) -> str:
    # the LLVM aggregate that a tupleret function returns: its tuple's n slots, then, where some
    # return of it is a constant tuple (c: Gen.vconst), that tuple's address, null where it
    # returns a new one, which its wrapper makes of the slots
    return "{" + ", ".join(["i64" for _ in range(n)] + (["ptr"] if c else [])) + "}"

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
    while ci.base in self.classes and k < len(self.classes[ci.base].fields) + self.classes[ci.base].nflag + self.classes[ci.base].nbox:
        ci = self.classes[ci.base]
    key = f"{ci.name} {k}"
    if key not in self.tbaa:
        if ci.name not in self.tbaacls:  # (once a class: its struct has as many members as fields)
            self.tbaacls[ci.name] = len([t for t in struct_types(ci) if t not in TBAA_SIZES]) == 0
        if not self.tbaacls[ci.name]:
            return ""
        self.tbaa[key] = TBAA_FIELDS + len(self.tbaa)
    return f", !tbaa !{self.tbaa[key]}"

def gen_list_tag(self, what: str) -> str:
    # the TBAA of an inline access to a list's length ("len": the header's first word), its items
    # pointer ("items": the third) or one of its items ("slot"), with listguard: ", !tbaa !N",
    # numbered as fieldtbaa numbers a field's (Gen.tbaa). They share fieldtbaa's root, as members of
    # structs of their own ("@list", runtime.c's List, and "@slot", one item), which no class lays
    # out: LLVM tells an item from a length or an items pointer and all three from any object's
    # field, so that a loop that stores items keeps its lists' lengths and items pointers in
    # registers. The driver gives runtime.c's accesses through its List and Slot the same tags
    # (retag_runtime_lists), so inlined runtime code's are told apart too. runtime.py has no such
    # tags (lower_module's runtime mode)
    if "listguard" not in self.opts or self.rtmode:
        return ""
    key = "@list 2" if what == "items" else "@list 0" if what == "len" else "@slot 0"
    if key not in self.tbaa:
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
            o.append(f"  {tmpname(i.r[0])} = load {lt(i.t)}, ptr {i.a[0].v}{metadata}")
        else:
            o.append(f"  store {lt(i.a[1].t)} {i.a[1].v}, ptr {i.a[0].v}{metadata}")
    elif op == "mach.addr":
        o.append(f"  {tmpname(i.r[0])} = getelementptr{' inbounds' if i.k == 1 else ''} {lt(i.s)}, ptr {i.a[0].v}, i64 {i.a[1].v}")
    elif op == "mem.load":
        o.append(f"  {tmpname(i.r[0])} = load {'ptr' if i.t == 'None' else lt(i.t)}, ptr {i.a[0].v}{self.ftags.get(i.a[0].v, '')}")
    elif op == "mem.store":
        v = i.a[1]
        o.append(f"  store {'ptr' if v.t == 'None' else lt(v.t)} {v.v}, ptr {i.a[0].v}{self.ftags.get(i.a[0].v, '')}")
    elif op == "field.addr":
        self.rangeused = self.rangeused or i.a[0].t == RANGEC
        self.objectused = self.objectused or i.a[0].t == OBJECTC
        o.append(f"  {tmpname(i.r[0])} = getelementptr %C.{i.a[0].t}, ptr {i.a[0].v}, i32 0, i32 {i.k}")
        if "fieldtbaa" in self.opts:
            self.ftags[tmpname(i.r[0])] = self.field_tag(i.a[0].t, i.k)
    elif op == "alloc.fixed":
        self.rangeused = self.rangeused or i.t == RANGEC
        self.objectused = self.objectused or i.t == OBJECTC
        size = str(8 * tslots(i.t)) if is_tuple(i.t) else f"ptrtoint (ptr getelementptr (%C.{i.t}, ptr null, i32 1) to i64)"
        if tmpname(i.r[0]) not in self.vtuples:  # (a tuple returned by value is never made: tupleret)
            o.append(f"  {tmpname(i.r[0])} = {self.alloc_call(size, i.t)}")
    elif op == "vtuple.make":
        # The runtime VTuple layout is a length followed by 8-byte item slots.
        # Keep the scanned allocator and its GC boundary, including for scalar
        # items. References remain native pointer operands live across that call.
        # Address and bool-widening temporaries belong only to this emitter.
        p = tmpname(i.r[0])
        o.append(f"  {p} = {self.alloc_call(str(8 * (len(i.a) + 1)), i.t)}")
        o.append(f"  store i64 {len(i.a)}, ptr {p}")
        for k in range(len(i.a)):
            v = i.a[k]
            a = f"%vt.{i.r[0]}.{k}"
            o.append(f"  {a} = getelementptr i64, ptr {p}, i64 {k + 1}")
            if v.t == "bool":
                o.append(f"  {a}.value = zext i1 {v.v} to i64")
                o.append(f"  store i64 {a}.value, ptr {a}")
            else:
                o.append(f"  store {'ptr' if v.t == 'None' else lt(v.t)} {v.v}, ptr {a}")
    elif op == "tuple.store" and i.a[0].v in self.vtuples:
        self.vslots[f"{i.a[0].v} {i.k}"] = i.a[1].v  # (the slot its ret returns)
    elif op == "tuple.load" and i.a[0].v in self.vaggs:
        o.append(f"  {tmpname(i.r[1])} = extractvalue {self.vaggs[i.a[0].v]} {i.a[0].v}, {i.k}")
    elif op == "tuple.load" or op == "tuple.store":
        o.append(f"  {tmpname(i.r[0])} = getelementptr i64, ptr {i.a[0].v}, i64 {i.k}")
        if op == "tuple.load":
            o.append(f"  {tmpname(i.r[1])} = load i64, ptr {tmpname(i.r[0])}")
        else:
            o.append(f"  store i64 {i.a[1].v}, ptr {tmpname(i.r[0])}")
    elif op == "slot.pack":
        v = i.a[0]
        c = f"bitcast double {v.v} to i64" if v.t == "float" else f"zext i1 {v.v} to i64" if v.t == "bool" else f"bitcast i64 {v.v} to i64" if v.t == "int" else f"ptrtoint ptr {v.v} to i64"
        o.append(f"  {tmpname(i.r[0])} = {c}")
    elif op == "slot.unpack":
        v = i.a[0]
        c = f"bitcast i64 {v.v} to double" if i.t == "float" else f"trunc i64 {v.v} to i1" if i.t == "bool" else f"bitcast i64 {v.v} to i64" if i.t == "int" else f"inttoptr i64 {v.v} to ptr"
        o.append(f"  {tmpname(i.r[0])} = {c}")
    elif op == "union.tag":
        o.append(f"  {tmpname(i.r[0])} = load i64, ptr {i.a[0].v}")
    elif op == "num.cast":
        v = i.a[0]
        c = f"zext i1 {v.v} to i64" if i.t == "int" else f"uitofp i1 {v.v} to double" if v.t == "bool" else f"sitofp i64 {v.v} to double"
        o.append(f"  {tmpname(i.r[0])} = {c}")
    elif op == "num.cmp":
        v = i.a[0]
        c = f"icmp {ICMP[i.s]} i64" if v.t == "int" else f"fcmp {FCMP[i.s]} double"
        o.append(f"  {tmpname(i.r[0])} = {c} {v.v}, {i.a[1].v}")
    elif op == "int.ucmp":
        o.append(f"  {tmpname(i.r[0])} = icmp u{ICMP[i.s][1:]} i64 {i.a[0].v}, {i.a[1].v}")
    elif op == "ptr.cmp":
        o.append(f"  {tmpname(i.r[0])} = icmp {ICMP[i.s]} ptr {i.a[0].v}, {i.a[1].v}")
    elif op == "union.payload" or op == "union.raw" or op == "dyn.payload" or op == "dyn.raw":
        o.append(f"  {tmpname(i.r[0])} = getelementptr i64, ptr {i.a[0].v}, i64 1")
        o.append(f"  {tmpname(i.r[1])} = load i64, ptr {tmpname(i.r[0])}")
    elif op == "dyn.type":
        o.append(f"  {tmpname(i.r[0])} = load ptr, ptr {i.a[0].v}")
    elif op == "big.make":
        o.append(f"  {tmpname(i.r[0])} = insertvalue {{i64, ptr}} undef, i64 {i.a[0].v}, 0")
        o.append(f"  {tmpname(i.r[1])} = insertvalue {{i64, ptr}} {tmpname(i.r[0])}, ptr {i.a[1].v}, 1")
    elif op == "big.lo" or op == "big.hi":
        o.append(f"  {tmpname(i.r[0])} = extractvalue {{i64, ptr}} {i.a[0].v}, {0 if op == 'big.lo' else 1}")
    elif op == "br":
        o.append(f"  br label %{i.b[0]}")
    elif op == "cbr":
        o.append(f"  br i1 {i.a[0].v}, label %{i.b[0]}, label %{i.b[1]}")
    elif op == "switch":
        o.append(f"  switch i64 {i.a[0].v}, label %{i.b[0]} [{' '.join([f'i64 {i.a[j].v}, label %{i.b[j]}' for j in range(1, len(i.a))])}]")
    elif op == "check":
        o.append(f"  br i1 {i.a[0].v}, label %{fn.cold[i.x if i.x != '' else i.s]}, label %{i.b[0]}")
    elif op == "phi":
        o.append(f"  {tmpname(i.r[0])} = phi {lt(i.t)} {', '.join([f'[{i.a[j].v}, %{i.b[j]}]' for j in range(len(i.a))])}")
    elif op == "ovf":
        r = i.r
        o.append(f"  {tmpname(r[0])} = call {{i64, i1}} @llvm.{CHECKED[i.s]}.with.overflow.i64(i64 {i.a[0].v}, i64 {i.a[1].v})")
        o.append(f"  {tmpname(r[1])} = extractvalue {{i64, i1}} {tmpname(r[0])}, 0")
        o.append(f"  {tmpname(r[2])} = extractvalue {{i64, i1}} {tmpname(r[0])}, 1")
    elif op == "select":
        x = i.a[1]
        y = i.a[2]
        o.append(f"  {tmpname(i.r[0])} = select i1 {i.a[0].v}, {lt(x.t)} {x.v}, {lt(y.t)} {y.v}")
    elif op == "ret" and len(i.a) > 0 and i.a[0].v.startswith("@tc.") and i.a[0].v in self.vtuples:
        # a constant tuple's slots and its address, by value (tupleret: vagg). Its promoting int
        # items are 64-bit literals (Gen.tuple_const): their Mpz words, past the items, are 0
        n = tslots(fn.f.ret)
        slots = ["i64 " + const_slot(x) for x in self.tconstdata[i.a[0].v].items]
        slots = slots + ["i64 0" for _ in range(n - len(slots))]
        o.append(f"  ret {vagg(n, True)} {{{', '.join(slots + ['ptr ' + i.a[0].v])}}}")
    elif op == "ret" and len(i.a) > 0 and i.a[0].v in self.vtuples:
        # the tuple's slots, by value (tupleret): what its tuple.stores gave each, else the zero
        # of the tuple that alloc.fixed would have made (and a null constant's address: vagg)
        n = tslots(fn.f.ret)
        agg = vagg(n, fn.f.ll in self.vconst)
        cur = "zeroinitializer"
        for k in range(n):
            s = self.vslots.get(i.a[0].v + " " + str(k), "0")
            o.append(f"  {i.a[0].v}.v{k} = insertvalue {agg} {cur}, i64 {s}, {k}")
            cur = f"{i.a[0].v}.v{k}"
        o.append(f"  ret {agg} {cur}")
    elif op == "ret":
        o.append(f"  ret {lt(i.a[0].t)} {i.a[0].v}" if len(i.a) > 0 else "  ret void")
    elif op == "ret.none":
        # (None: null, but a dynamic value's, which is its constant box: dynamic.py)
        o.append("  ret void" if fn.f.ret == "None" else f"  ret ptr {self.rtdata('pys_dyn_none_box')}" if fn.f.ret == "dyn" else "  ret ptr null")
    elif op == "raise":
        o.append(f"  call void @pys_raise(ptr {i.a[0].v}, ptr {i.a[1].v})")
        o.append("  unreachable")
    elif op == "unreachable":
        o.append("  unreachable")
    elif op == "rt" and not self.rtmode and i.s.startswith("recursion."):
        # The native depth accounting's state is the program's, even where the runtime is a
        # separate library (lower_module's recursion_ir): a depth snapshot or restoration
        # is a plain load or store with the state's own TBAA tag; an entry or a generator
        # resume's leaving calls the module's helper, which LLVM inlines. Closed recursion's
        # entry checks the depth its caller passed and counts in a register, and its
        # restorations go: the word stays as the cycle's outermost call found it
        if fn.f.ll in self.rdpass and i.s == "recursion.enter" and len(i.r) == 1 and tmpname(i.r[0]) == fn.rdepth:
            o.append(f"  {tmpname(i.r[0])} = {self.invoke('call i64 @pys.recursion.check(i64 %rd)', i)}")
        elif fn.f.ll in self.rdpass and i.s == "recursion.restore":
            return
        elif i.s == "recursion.restore" and len(i.b) == 0:
            o.append(f"  store i64 {i.a[0].v}, ptr @pys_recursion_state, !tbaa !{TBAA_DEPTH}")
        elif i.s == "recursion.depth" and len(i.b) == 0:
            o.append(f"  {tmpname(i.r[0])} = load i64, ptr @pys_recursion_state, !tbaa !{TBAA_DEPTH}")
        else:
            ll = self.rtfns[i.s].ll
            c = self.invoke(f"call {ll[0]} @pys.{i.s}({', '.join([ll[j + 1] + ' ' + i.a[j].v for j in range(len(i.a))])})", i)
            o.append("  " + c if ll[0] == "void" else f"  {tmpname(i.r[0])} = {c}")
            if i.s == "recursion.enter":
                self.entries = True
            elif i.s == "recursion.resume":
                self.resumes_counted = True
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
            vs[0] = f"i64 {self.key_kind(targs(h)[0] if is_dict(h) else selem(h), is_dict(h)) if h != '' else '0'}"
        c = self.invoke(f"call {ll[0]} @{f.sym}({', '.join(vs)})", i)
        o.append("  " + c if ll[0] == "void" else f"  {tmpname(i.r[0])} = {c}")
    elif op == "call" and i.s in self.rdpass and fn.f.ll in self.rdpass:
        # (closed recursion: a call within the cycle gives the callee's body this function's depth)
        c = self.invoke(f"call {lt(i.t)} @r.{i.s[1:]}({', '.join([lt(v.t) + ' ' + v.v for v in i.a] + ['i64 ' + fn.rdepth])})", i)
        o.append("  " + c if i.t == "None" else f"  {tmpname(i.r[0])} = {c}")
    elif op == "call" and len(i.r) == 1 and f"{fn.f.ll} {tmpname(i.r[0])}" in self.vcalls:
        # the slots of the tuple a function returns, by value, to tuple.loads alone (tupleret)
        agg = vagg(self.vrets[i.s], i.s in self.vconst)
        args = ", ".join([lt(v.t) + " " + v.v for v in i.a])
        inline = " alwaysinline" if i.x == "inline" else ""
        o.append(f"  {tmpname(i.r[0])} = {self.invoke(f'call {agg} @v.{i.s[1:]}({args}){inline}', i)}")
        self.vaggs[tmpname(i.r[0])] = agg
    elif op == "call":
        # (alwaysinline: listguard's copy of its callee's only call, which LLVM would inline)
        inline = " alwaysinline" if i.x == "inline" else ""
        c = self.invoke(f"call {lt(i.t)} {i.s}({', '.join([lt(v.t) + ' ' + v.v for v in i.a])}){inline}", i)
        o.append("  " + c if i.t == "None" else f"  {tmpname(i.r[0])} = {c}")
    elif op == "icall":
        # a Callable's code (operand 0), called with its env and the arguments
        c = self.invoke(f"call {lt(i.t)} {i.a[0].v}({', '.join([lt(v.t) + ' ' + v.v for v in i.a[1:]])})", i)
        o.append("  " + c if i.t == "None" else f"  {tmpname(i.r[0])} = {c}")
    elif op == "init":
        o.append("  " + self.invoke(f"call void @init.{i.s}()", i))
    elif op == "empty.kind":
        # Only fresh empty results may change their dict/set key layout. A later
        # return can resolve the hole; an outer caller types an unresolved result.
        t = self.holes[i.k] if i.k > 0 else i.a[0].t
        kind = self.key_kind(targs(t)[0] if is_dict(t) else selem(t), is_dict(t), True) if t != "" else "0"
        o.append(f"  {tmpname(i.r[0])} = getelementptr i64, ptr {i.a[0].v}, i64 1")
        o.append(f"  store i64 {kind}, ptr {tmpname(i.r[0])}")
    elif op == "list.len":
        # (never negative: LISTLEN_RANGE, which lets LLVM fold an index's negative and upper tests into one)
        rng = ""
        if not self.rtmode:
            rng = f", !range !{LISTLEN_RANGE}"
            self.listlen = True
        o.append(f"  {tmpname(i.r[0])} = load i64, ptr {i.a[0].v}{self.list_tag('len')}{rng}")
    elif op == "list.load":
        # the item of a list at an index within its length (listget): l->a[index], as runtime.c
        # lays a List out ({len, cap, a}), in the 8-byte slot pys_list_get would have returned
        r = i.r
        o.append(f"  {tmpname(r[1])} = getelementptr inbounds {{i64, i64, ptr}}, ptr {i.a[0].v}, i64 0, i32 2")
        o.append(f"  {tmpname(r[2])} = load ptr, ptr {tmpname(r[1])}{self.list_tag('items')}")
        o.append(f"  {tmpname(r[3])} = getelementptr inbounds i64, ptr {tmpname(r[2])}, i64 {i.a[1].v}")
        o.append(f"  {tmpname(r[0])} = load i64, ptr {tmpname(r[3])}{self.list_tag('slot')}")
    elif op == "list.store":
        # l->a[index] = item, at an index within its length (listguard), as pys_list_set stores it
        # where the list has no identity companion (ircheck: no list of the program has one)
        r = i.r
        o.append(f"  {tmpname(r[0])} = getelementptr inbounds {{i64, i64, ptr}}, ptr {i.a[0].v}, i64 0, i32 2")
        o.append(f"  {tmpname(r[1])} = load ptr, ptr {tmpname(r[0])}{self.list_tag('items')}")
        o.append(f"  {tmpname(r[2])} = getelementptr inbounds i64, ptr {tmpname(r[1])}, i64 {i.a[1].v}")
        o.append(f"  store i64 {i.a[2].v}, ptr {tmpname(r[2])}{self.list_tag('slot')}")
    elif op == "landing":
        r = i.r
        o.append(f"  {tmpname(r[0])} = landingpad {{ ptr, i32 }} catch ptr null")
        o.append(f"  {tmpname(r[1])} = extractvalue {{ ptr, i32 }} {tmpname(r[0])}, 0")
        o.append(f"  store ptr {tmpname(r[1])}, ptr {i.a[0].v}")
        o.append(f"  br label %{i.b[0]}")
    elif op == "throw":
        o.append(f"  call void @pys_throw(ptr {i.a[0].v})")
        o.append("  unreachable")
    elif op == "exc.match":
        o.append(f"  {tmpname(i.r[0])} = call i64 @pys_exc_in(ptr {i.a[0].v}, ptr {i.a[1].v})")
        o.append(f"  {tmpname(i.r[1])} = icmp ne i64 {tmpname(i.r[0])}, 0")
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
        o.append(f"  store [{promise_slots(self.gproto)} x i64] zeroinitializer, ptr %coro.promise")
        o.append(f"  %coro.name = getelementptr i64, ptr %coro.promise, i64 {GENNAME}")
        o.append(f"  store ptr {i.a[0].v}, ptr %coro.name")
        if self.gproto:
            # (not started: what send() and throw() tell from a generator suspended at a yield)
            o.append(f"  %coro.new = getelementptr i64, ptr %coro.promise, i64 {GENSTATE}")
            o.append(f"  store i64 {GENNEW}, ptr %coro.new")
        o.append("  %coro.first = call i8 @llvm.coro.suspend(token none, i1 false)")
        o.append(f"  switch i8 %coro.first, label %coro.ret [i8 0, label %{i.b[0]} i8 1, label %coro.cleanup]")
    elif op == "gen.yield":
        # the value in the promise (and an int's pointer, GENVALP), the state (k: whether closing it
        # here runs code of its), suspend
        o.append(f"  store i64 {i.a[0].v}, ptr %coro.promise")
        if len(i.a) > 1:
            o.append(f"  {tmpname(i.r[0])}.hi = getelementptr i64, ptr %coro.promise, i64 {GENVALP}")
            o.append(f"  store ptr {i.a[1].v}, ptr {tmpname(i.r[0])}.hi")
        o.append(f"  {tmpname(i.r[0])} = getelementptr i64, ptr %coro.promise, i64 {GENSTATE}")
        o.append(f"  store i64 {i.k}, ptr {tmpname(i.r[0])}")
        o.append(f"  {tmpname(i.r[1])} = call i8 @llvm.coro.suspend(token none, i1 false)")
        o.append(f"  switch i8 {tmpname(i.r[1])}, label %coro.ret [i8 0, label %{i.b[0]} i8 1, label %coro.cleanup]")
    elif op == "gen.ret":
        # the value returned, finished; then the final suspend, which LLVM requires to be one
        o.append(f"  {tmpname(i.r[0])} = getelementptr i64, ptr %coro.promise, i64 {GENRET}")
        if len(i.a) > 0:
            o.append(f"  store i64 {i.a[0].v}, ptr {tmpname(i.r[0])}")
        elif fn.f.gret == "dyn":
            # A bare return/fallthrough yields None, a real box in an Any
            # return channel. The final type may be inferred after this op.
            o.append(f"  store ptr {self.rtdata('pys_dyn_none_box')}, ptr {tmpname(i.r[0])}")
        if len(i.a) > 1:
            o.append(f"  {tmpname(i.r[0])}.hi = getelementptr i64, ptr %coro.promise, i64 {GENRETP}")
            o.append(f"  store ptr {i.a[1].v}, ptr {tmpname(i.r[0])}.hi")
        o.append(f"  {tmpname(i.r[1])} = getelementptr i64, ptr %coro.promise, i64 {GENSTATE}")
        o.append(f"  store i64 {GENDONE}, ptr {tmpname(i.r[1])}")
        o.append("  br label %coro.final")
    elif op == "gen.promise":
        if len(i.a) == 0:
            o.append(f"  {tmpname(i.r[0])} = getelementptr i64, ptr %coro.promise, i64 0")
        else:
            o.append(f"  {tmpname(i.r[0])} = call ptr @llvm.coro.promise(ptr {i.a[0].v}, i32 8, i1 false)")
    elif op == "gen.resume":
        o.append("  " + self.invoke(f"call void @llvm.coro.resume(ptr {i.a[0].v})", i))
    elif op == "gen.drop" and not self.rtmode and i.a[0].t not in self.genplain:
        # (a generator whose body can recur, Gen.recursionscope: its cleanup counts as a frame)
        o.append(f"  call void @pys.gen.drop.counted(ptr {i.a[0].v})")
        self.gendrops_counted = True
        for name in ["pys_recursion_enter", "pys_recursion_leave", "pys_recursion_depth", "pys_recursion_restore",
                     "pys_try_mark", "pys_exc_begin", "pys_gen_unraisable", "pys_personality"]:
            self.runtime(name)
    elif op == "gen.drop":
        o.append(f"  call void @pys.gen.drop(ptr {i.a[0].v})")
        self.gendrops = True
    else:
        fail(f"internal error: no lowering for IR op {op}", 0)

def promise_slots(gproto: bool) -> int:
    # the i64 slots of a generator's promise (specs.GENSLOTS): seven in a program that uses send()
    # or throw(), nine where a module opts in to promoting ints
    return GENSLOTSB if int_program() else GENSLOTSX if gproto else GENSLOTS

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
                i.line = t.line
                i.a = [t.a[0], t.a[1], Val("null", "str")]
                i.r = one_num(fn.n)
                self.runtime("pys_exc_new")
                code.append(i)
                ex = tmpname(fn.n)
            st = Ins("mach.store", "", "")
            st.line = t.line
            st.a = [Val(lp.a[0].v, "%ptr"), Val(ex, "%ptr")]
            code.append(st)
            br = Ins("br", "", "")
            br.line = t.line
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
    self.out.append(f"  {tmpname(i.r[0])} = {s}")

