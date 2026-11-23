"""Make the references a linked WebAssembly module keeps in locals visible to the collector.

usage: python3 wasm/spill_roots.py [--no-spill] IN.wasm OUT.wasm
       (--no-spill: collection on, nothing spilled; the control that shows the spills matter)

runtime.c's collector finds the program's references by scanning the stack conservatively, but
WebAssembly keeps most values in locals and on the operand stack, which nothing can read
(wasm/README.md). This pass rewrites a command that wasm-ld linked from LLVM's output. Around
each call that may reach the collector, it reserves a frame below __stack_pointer and stores in
it every i32 and i64 local that is live after the call, and every i32 and i64 value beneath the
call's arguments on the operand stack; the call's return releases the frame. The collector
scans that stack up to __stack_high, and a frame holds only what is live while its call runs.
Finally the pass makes runtime.c's wasi_roots_spilled return 1, which lets gc_init turn
collection on.

A call may reach the collector if its callee is mark_roots or calls it, directly or through
another function, or if it is a call_indirect or calls an import that WASI does not provide.
The analysis follows legacy and try_table exception handling: a call inside a try can continue
at the try's catches, so what they read is live during the call. An exception skips the frame's
release; the function that catches it restores __stack_pointer (LLVM's landing pads do), which
releases the frames the exception left. The pass fails, and the build with it, on input that it
does not model: SIMD, tail calls, or a value of a type it can spill that an enclosing block
keeps on the operand stack across a call.
"""
import sys

I32 = 0x7F
I64 = 0x7E
F32 = 0x7D
F64 = 0x7C
V128 = 0x7B
ANY = 0                       # a value popped from the polymorphic stack of unreachable code
VALTYPES = (I32, I64, F32, F64, V128, 0x70, 0x6F, 0x69)   # the numeric types, funcref, externref, exnref
WASI_MODULES = ("wasi_snapshot_preview1", "wasi_unstable")
COLLECTOR = "mark_roots"      # runtime.c: every collection scans the stack here
FLAG = "wasi_roots_spilled"   # runtime.c: returns 1 once this pass has run


class Unsupported(Exception):
    pass


def uleb(b: bytes, p: int) -> tuple:
    r = 0
    s = 0
    while True:
        x = b[p]
        p += 1
        r |= (x & 0x7F) << s
        s += 7
        if x < 0x80:
            return r, p


def sleb(b: bytes, p: int) -> tuple:
    r = 0
    s = 0
    while True:
        x = b[p]
        p += 1
        r |= (x & 0x7F) << s
        s += 7
        if x < 0x80:
            if x & 0x40:
                r -= 1 << s
            return r, p


def put_uleb(out: bytearray, v: int) -> None:
    while True:
        x = v & 0x7F
        v >>= 7
        if v:
            out.append(x | 0x80)
        else:
            out.append(x)
            return


def put_sleb(out: bytearray, v: int) -> None:
    while True:
        x = v & 0x7F
        v >>= 7
        if (v == 0 and not x & 0x40) or (v == -1 and x & 0x40):
            out.append(x)
            return
        out.append(x | 0x80)


# ---------- instruction stack effects ----------

SIMPLE: dict = {}             # opcode -> (values popped, types pushed), for operators without control or indices


def simple(lo: int, hi: int, pops: int, pushes: tuple) -> None:
    for op in range(lo, hi + 1):
        SIMPLE[op] = (pops, pushes)


simple(0x45, 0x45, 1, (I32,))
simple(0x46, 0x4F, 2, (I32,))
simple(0x50, 0x50, 1, (I32,))
simple(0x51, 0x66, 2, (I32,))
simple(0x67, 0x69, 1, (I32,))
simple(0x6A, 0x78, 2, (I32,))
simple(0x79, 0x7B, 1, (I64,))
simple(0x7C, 0x8A, 2, (I64,))
simple(0x8B, 0x91, 1, (F32,))
simple(0x92, 0x98, 2, (F32,))
simple(0x99, 0x9F, 1, (F64,))
simple(0xA0, 0xA6, 2, (F64,))
simple(0xA7, 0xAB, 1, (I32,))
simple(0xAC, 0xB1, 1, (I64,))
simple(0xB2, 0xB6, 1, (F32,))
simple(0xB7, 0xBB, 1, (F64,))
simple(0xBC, 0xBC, 1, (I32,))
simple(0xBD, 0xBD, 1, (I64,))
simple(0xBE, 0xBE, 1, (F32,))
simple(0xBF, 0xBF, 1, (F64,))
simple(0xC0, 0xC1, 1, (I32,))
simple(0xC2, 0xC4, 1, (I64,))
simple(0x1A, 0x1A, 1, ())                      # drop
simple(0x3F, 0x3F, 0, (I32,))                  # memory.size
simple(0x40, 0x40, 1, (I32,))                  # memory.grow
simple(0xD1, 0xD1, 1, (I32,))                  # ref.is_null
LOADS = {0x28: I32, 0x29: I64, 0x2A: F32, 0x2B: F64, 0x2C: I32, 0x2D: I32, 0x2E: I32, 0x2F: I32,
         0x30: I64, 0x31: I64, 0x32: I64, 0x33: I64, 0x34: I64, 0x35: I64}
for _op in range(0x36, 0x3F):
    SIMPLE[_op] = (2, ())                      # stores
for _op in LOADS:
    SIMPLE[_op] = (1, (LOADS[_op],))
MISC = {0: (1, (I32,)), 1: (1, (I32,)), 2: (1, (I32,)), 3: (1, (I32,)), 4: (1, (I64,)), 5: (1, (I64,)),
        6: (1, (I64,)), 7: (1, (I64,)), 8: (3, ()), 9: (0, ()), 10: (3, ()), 11: (3, ()), 12: (3, ()),
        13: (0, ()), 14: (3, ()), 15: (2, (I32,)), 16: (0, (I32,)), 17: (3, ())}   # 0xFC: saturating
#                    truncations, then memory.init, data.drop, memory.copy, memory.fill, table.init,
#                    elem.drop, table.copy, table.grow, table.size, table.fill
MISC_IMMEDIATES = {8: 2, 9: 1, 10: 2, 11: 1, 12: 2, 13: 1, 14: 2, 15: 1, 16: 1, 17: 1}


# ---------- the module ----------

class Module:
    def __init__(self, data: bytes):
        if data[:8] != b"\0asm\1\0\0\0":
            raise Unsupported("not a WebAssembly module")
        self.data = data
        self.sections: list = []               # (id, payload)
        self.types: list = []                  # (params, results)
        self.func_types: list = []             # type of each function, imports first
        self.func_imports: list = []           # the module each imported function comes from
        self.global_types: list = []
        self.tag_types: list = []
        self.func_names: dict = {}
        self.global_names: dict = {}
        p = 8
        while p < len(data):
            sid = data[p]
            size, q = uleb(data, p + 1)
            self.sections.append((sid, data[q:q + size]))
            p = q + size
        for sid, pay in self.sections:
            if sid == 1:
                self.read_types(pay)
            elif sid == 2:
                self.read_imports(pay)
            elif sid == 3:
                n, q = uleb(pay, 0)
                for _ in range(n):
                    t, q = uleb(pay, q)
                    self.func_types.append(t)
            elif sid == 6:
                self.read_globals(pay)
            elif sid == 13:
                n, q = uleb(pay, 0)
                for _ in range(n):
                    t, q = uleb(pay, q + 1)
                    self.tag_types.append(t)
            elif sid == 0:
                self.read_custom(pay)

    def valtype(self, v: int) -> int:
        if v not in VALTYPES:
            raise Unsupported(f"value type 0x{v:02x}")
        return v

    def read_types(self, pay: bytes) -> None:
        n, p = uleb(pay, 0)
        for _ in range(n):
            if pay[p] != 0x60:
                raise Unsupported(f"type form 0x{pay[p]:02x}")
            k, p = uleb(pay, p + 1)
            params = [self.valtype(v) for v in pay[p:p + k]]
            p += k
            k, p = uleb(pay, p)
            results = [self.valtype(v) for v in pay[p:p + k]]
            p += k
            self.types.append((params, results))

    def read_imports(self, pay: bytes) -> None:
        n, p = uleb(pay, 0)
        for _ in range(n):
            k, p = uleb(pay, p)
            mod = pay[p:p + k].decode()
            p += k
            k, p = uleb(pay, p)
            p += k
            kind = pay[p]
            p += 1
            if kind == 0:
                t, p = uleb(pay, p)
                self.func_types.append(t)
                self.func_imports.append(mod)
            elif kind == 1:
                p = skip_limits(pay, p + 1)
            elif kind == 2:
                p = skip_limits(pay, p)
            elif kind == 3:
                self.global_types.append(self.valtype(pay[p]))
                p += 2
            elif kind == 4:
                t, p = uleb(pay, p + 1)
                self.tag_types.append(t)
            else:
                raise Unsupported(f"import kind {kind}")

    def read_globals(self, pay: bytes) -> None:
        n, p = uleb(pay, 0)
        for _ in range(n):
            self.global_types.append(self.valtype(pay[p]))
            p += 2
            while pay[p] != 0x0B:              # the initializer: constants, global.get, ref.*, i32/i64 add/sub/mul
                op = pay[p]
                p += 1
                if op in (0x41, 0x42):
                    _, p = sleb(pay, p)
                elif op == 0x43:
                    p += 4
                elif op == 0x44:
                    p += 8
                elif op in (0x23, 0xD2):
                    _, p = uleb(pay, p)
                elif op == 0xD0:
                    p += 1
                elif op not in (0x6A, 0x6B, 0x6C, 0x7C, 0x7D, 0x7E):
                    raise Unsupported(f"global initializer opcode 0x{op:02x}")
            p += 1

    def read_custom(self, pay: bytes) -> None:
        k, p = uleb(pay, 0)
        if pay[p:p + k] != b"name":
            return
        p += k
        while p < len(pay):
            sub = pay[p]
            size, q = uleb(pay, p + 1)
            end = q + size
            if sub in (1, 7):
                names = self.func_names if sub == 1 else self.global_names
                n, q = uleb(pay, q)
                for _ in range(n):
                    i, q = uleb(pay, q)
                    k, q = uleb(pay, q)
                    names[i] = pay[q:q + k].decode("utf-8", "replace")
                    q += k
            p = end

    def block_sig(self, bt: int) -> tuple:
        if bt >= 0:
            return self.types[bt]
        if bt == -64:
            return [], []
        return [], [self.valtype(bt + 128)]


def skip_limits(pay: bytes, p: int) -> int:
    flags = pay[p]
    _, p = uleb(pay, p + 1)
    if flags & 1:
        _, p = uleb(pay, p)
    return p


# ---------- one function ----------

class Frame:
    def __init__(self, kind: str, height: int, params: list, results: list, target: int, end_block: int):
        self.kind = kind                       # func, block, loop, if, try or try_table
        self.height = height                   # the operand stack's height under the frame's params
        self.params = params
        self.results = results
        self.target = target                   # where a branch to the frame's label goes
        self.end_block = end_block             # where the code after its end starts
        self.cond_block = -1                   # if: the block that tests the condition
        self.has_else = False
        self.dead = False                      # the rest of the current section is unreachable
        self.dead_entry = False                # the frame itself is unreachable
        self.handlers: list = []               # try: its catches' blocks
        self.throwers: list = []               # try: blocks ending in a call or throw inside it
        self.catch_targets: list = []          # try_table: the blocks its catch clauses branch to


class Site:
    """A reachable call: where, its callee, its blocks, and what the operand stack holds."""

    def __init__(self, offset: int, end: int, block: int, nxt: int, callee: int, args: list, beneath: list,
                 crossing: bool):
        self.offset = offset                   # of the call
        self.end = end                         # of the instruction after it
        self.block = block                     # the block it ends
        self.nxt = nxt                         # the block where it returns; the others after it are catches
        self.callee = callee                   # -1: a call_indirect
        self.args = args
        self.beneath = beneath                 # the frame's values under the arguments
        self.crossing = crossing               # an enclosing block holds an i32 or i64 on the stack


class Function:
    def __init__(self, m: Module, index: int, body: bytes, sp: int):
        self.m = m
        self.index = index
        self.body = body
        self.sp = sp
        params, self.results = m.types[m.func_types[index]]
        self.ltypes = list(params)
        self.nparams = len(params)
        n, p = uleb(body, 0)
        self.groups: list = []
        for _ in range(n):
            k, p = uleb(body, p)
            t = m.valtype(body[p])
            p += 1
            self.groups.append((k, t))
            self.ltypes.extend([t] * k)
        self.code_start = p
        self.succ: list = []
        self.use: list = []
        self.kill: list = []
        self.sites: list = []
        self.stack: list = []                  # the operand stack's types, during the walk
        self.frames: list = []                 # its control frames

    def block(self) -> int:
        self.succ.append([])
        self.use.append(0)
        self.kill.append(0)
        return len(self.succ) - 1

    def edge(self, a: int, b: int) -> None:
        if b not in self.succ[a]:
            self.succ[a].append(b)

    # the walk: blocks, liveness inputs, and the sites that need spills
    def walk(self) -> None:
        m = self.m
        b = self.body
        exit_block = self.block()
        cur = self.block()
        stack = self.stack
        frames = self.frames
        frames.append(Frame("func", 0, [], self.results, exit_block, exit_block))
        pop = self.pop
        p = self.code_start
        while True:
            f = frames[-1]
            at = p
            op = b[p]
            p += 1
            if op in SIMPLE:
                if 0x28 <= op <= 0x3E:
                    a, p = uleb(b, p)
                    if a & 0x40:
                        _, p = uleb(b, p)
                    _, p = uleb(b, p)
                elif op in (0x3F, 0x40):
                    p += 1
                pops, pushes = SIMPLE[op]
                for _ in range(pops):
                    pop()
                stack.extend(pushes)
            elif op == 0x20 or op == 0x21 or op == 0x22:
                x, p = uleb(b, p)
                t = self.ltypes[x]
                bit = 1 << x if t == I32 or t == I64 else 0
                if op == 0x20:
                    if not self.kill[cur] & bit:
                        self.use[cur] |= bit
                    stack.append(t)
                else:
                    pop()
                    self.kill[cur] |= bit
                    if op == 0x22:
                        stack.append(t)
            elif op in (0x41, 0x42):
                _, p = sleb(b, p)
                stack.append(I32 if op == 0x41 else I64)
            elif op == 0x43:
                p += 4
                stack.append(F32)
            elif op == 0x44:
                p += 8
                stack.append(F64)
            elif op == 0x23:
                x, p = uleb(b, p)
                stack.append(m.global_types[x])
            elif op == 0x24:
                _, p = uleb(b, p)
                pop()
            elif op == 0x10 or op == 0x11:
                if op == 0x10:
                    callee, p = uleb(b, p)
                    ptypes, rtypes = m.types[m.func_types[callee]]
                else:
                    t, p = uleb(b, p)
                    _, p = uleb(b, p)
                    ptypes, rtypes = m.types[t]
                    ptypes = ptypes + [I32]   # the table index, above the arguments
                    callee = -1
                for _ in ptypes:
                    pop()
                if f.dead:
                    stack.extend(rtypes)
                else:
                    crossing = False
                    for g in range(len(frames) - 1):
                        for t in stack[frames[g].height:frames[g + 1].height]:
                            if t == I32 or t == I64:
                                crossing = True
                    beneath = stack[f.height:]
                    stack.extend(rtypes)
                    self.throw_edges(frames, cur)
                    nxt = self.block()
                    self.edge(cur, nxt)
                    self.sites.append(Site(at, p, cur, nxt, callee, list(ptypes), beneath, crossing))
                    cur = nxt
            elif op == 0x02 or op == 0x03 or op == 0x04 or op == 0x06:
                bt, p = sleb(b, p)
                params, results = m.block_sig(bt)
                if op == 0x04:
                    pop()
                for _ in params:
                    pop()
                h = len(stack)
                stack.extend(params)
                end_block = self.block()
                if op == 0x03:
                    head = self.block()
                    if not f.dead:
                        self.edge(cur, head)
                    nf = Frame("loop", h, params, results, head, end_block)
                    cur = head
                elif op == 0x04:
                    nf = Frame("if", h, params, results, end_block, end_block)
                    nf.cond_block = cur
                    then = self.block()
                    if not f.dead:
                        self.edge(cur, then)
                    cur = then
                elif op == 0x06:
                    nf = Frame("try", h, params, results, end_block, end_block)
                    body = self.block()
                    if not f.dead:
                        self.edge(cur, body)
                    cur = body
                else:
                    nf = Frame("block", h, params, results, end_block, end_block)
                nf.dead = nf.dead_entry = f.dead   # inside unreachable code, unreachable too
                frames.append(nf)
            elif op == 0x1F:                   # try_table
                bt, p = sleb(b, p)
                params, results = m.block_sig(bt)
                n, p = uleb(b, p)
                targets = []
                for _ in range(n):
                    kind = b[p]
                    p += 1
                    if kind in (0, 1):
                        _, p = uleb(b, p)
                    label, p = uleb(b, p)
                    targets.append(frames[-1 - label].target)
                for _ in params:
                    pop()
                h = len(stack)
                stack.extend(params)
                end_block = self.block()
                nf = Frame("try_table", h, params, results, end_block, end_block)
                nf.catch_targets = targets
                nf.dead = nf.dead_entry = f.dead
                body = self.block()
                if not f.dead:
                    self.edge(cur, body)
                cur = body
                frames.append(nf)
            elif op == 0x05:                   # else
                if not f.dead:
                    self.edge(cur, f.end_block)
                del stack[f.height:]
                stack.extend(f.params)
                f.has_else = True
                cur = self.block()
                f.dead = f.dead_entry
                if not f.dead:
                    self.edge(f.cond_block, cur)
            elif op == 0x07 or op == 0x19:     # catch, catch_all
                if op == 0x07:
                    tag, p = uleb(b, p)
                if not f.dead:
                    self.edge(cur, f.end_block)
                del stack[f.height:]
                if op == 0x07:
                    stack.extend(m.types[m.tag_types[tag]][0])
                cur = self.block()
                f.handlers.append(cur)
                f.dead = f.dead_entry
            elif op == 0x0B or op == 0x18:     # end, delegate
                if op == 0x18:
                    _, p = uleb(b, p)
                if not f.dead:
                    self.edge(cur, f.end_block)
                if f.kind == "if" and not f.has_else and not f.dead_entry:
                    self.edge(f.cond_block, f.end_block)
                for t in f.throwers:
                    for hb in f.handlers:
                        self.edge(t, hb)
                del stack[f.height:]
                stack.extend(f.results)
                frames.pop()
                if not frames:
                    if p != len(b):
                        raise Unsupported(f"function {self.index}: code after its end")
                    return
                cur = f.end_block
            elif op == 0x0C or op == 0x0D or op == 0x0E:
                if op == 0x0C:
                    label, p = uleb(b, p)
                    labels = [label]
                elif op == 0x0D:
                    label, p = uleb(b, p)
                    labels = [label]
                    pop()
                else:
                    n, p = uleb(b, p)
                    labels = []
                    for _ in range(n + 1):
                        label, p = uleb(b, p)
                        labels.append(label)
                    pop()
                if not f.dead:
                    for label in labels:
                        self.edge(cur, frames[-1 - label].target)
                if op == 0x0D:
                    nxt = self.block()
                    if not f.dead:
                        self.edge(cur, nxt)
                    cur = nxt
                else:
                    del stack[f.height:]
                    f.dead = True
                    cur = self.block()
            elif op == 0x0F:                   # return
                if not f.dead:
                    self.edge(cur, exit_block)
                del stack[f.height:]
                f.dead = True
                cur = self.block()
            elif op == 0x00:                   # unreachable
                del stack[f.height:]
                f.dead = True
                cur = self.block()
            elif op == 0x08 or op == 0x09 or op == 0x0A:   # throw, rethrow, throw_ref
                if op == 0x08:
                    tag, p = uleb(b, p)
                    for _ in m.types[m.tag_types[tag]][0]:
                        pop()
                elif op == 0x09:
                    _, p = uleb(b, p)
                else:
                    pop()
                if not f.dead:
                    self.throw_edges(frames, cur)
                del stack[f.height:]
                f.dead = True
                cur = self.block()
            elif op == 0x01:
                pass
            elif op == 0x1B:                   # select
                pop()
                x = pop()
                y = pop()
                stack.append(x if x != ANY else y)
            elif op == 0x1C:                   # select with types
                n, p = uleb(b, p)
                ts = [m.valtype(v) for v in b[p:p + n]]
                p += n
                pop()
                pop()
                pop()
                stack.extend(ts)
            elif op == 0x25 or op == 0x26:     # table.get, table.set
                _, p = uleb(b, p)
                pop()
                if op == 0x25:
                    stack.append(0x70)
                else:
                    pop()
            elif op == 0xD0:                   # ref.null
                stack.append(m.valtype(b[p]))
                p += 1
            elif op == 0xD2:                   # ref.func
                _, p = uleb(b, p)
                stack.append(0x70)
            elif op == 0xFC:
                sub, p = uleb(b, p)
                if sub not in MISC:
                    raise Unsupported(f"function {self.index}: opcode 0xfc {sub} at {at}")
                for _ in range(MISC_IMMEDIATES.get(sub, 0)):
                    _, p = uleb(b, p)
                pops, pushes = MISC[sub]
                for _ in range(pops):
                    pop()
                stack.extend(pushes)
            elif op == 0x12 or op == 0x13:
                raise Unsupported(f"function {self.index}: tail call at {at}")
            else:
                raise Unsupported(f"function {self.index}: opcode 0x{op:02x} at {at}")

    def pop(self) -> int:
        f = self.frames[-1]
        if len(self.stack) <= f.height:
            if f.dead:                         # (unreachable code's stack is polymorphic)
                return ANY
            raise Unsupported(f"function {self.index}: operand stack underflow")
        return self.stack.pop()

    def throw_edges(self, frames: list, cur: int) -> None:
        # a call or throw inside a try may continue at its catches (or an enclosing try's: every
        # enclosing try is assumed reachable, which can only add liveness)
        for g in frames:
            if g.kind == "try":
                g.throwers.append(cur)
            elif g.kind == "try_table":
                for t in g.catch_targets:
                    self.edge(cur, t)

    def liveness(self) -> list:
        n = len(self.succ)
        live_in = [0] * n
        live_out = [0] * n
        changed = True
        while changed:
            changed = False
            for i in range(n - 1, -1, -1):
                out = 0
                for s in self.succ[i]:
                    out |= live_in[s]
                live_out[i] = out
                v = self.use[i] | (out & ~self.kill[i])
                if v != live_in[i]:
                    live_in[i] = v
                    changed = True
        return live_in

    def reaches_return(self) -> list:
        """per block: whether the function can return normally from it"""
        n = len(self.succ)
        preds: list = [[] for _ in range(n)]
        for i in range(n):
            for j in self.succ[i]:
                preds[j].append(i)
        seen = [False] * n
        seen[0] = True
        work = [0]
        while work:
            for i in preds[work.pop()]:
                if not seen[i]:
                    seen[i] = True
                    work.append(i)
        return seen

    def rewrite(self, c_ret: list, c_any: list) -> bytes:
        """the body with frames around the calls that may collect: what a catch after the call
        reads if the callee may collect (c_any), and if it may also return afterwards (c_ret),
        what the code after the call reads, locals and the values under the arguments alike"""
        if not self.sites:
            return self.body
        live_in = self.liveness()
        nlocal = len(self.ltypes)
        frame = nlocal                         # new locals: the frame's address, then temporaries for
        extra: list = [I32]                    # the values a site lifts off the operand stack
        temps: dict = {}

        def temp(t: int, k: int) -> int:
            pool = temps.setdefault(t, [])
            while len(pool) <= k:
                pool.append(nlocal + len(extra))
                extra.append(t)
            return pool[k]

        inserts: list = []                     # (offset, order, code): code to insert before the offset
        for s in self.sites:
            if s.callee >= 0 and not c_any[s.callee]:
                continue
            returns = s.callee < 0 or c_ret[s.callee]
            bits = live_in[s.nxt] if returns else 0
            for h in self.succ[s.block]:
                if h != s.nxt:
                    bits |= live_in[h]
            live: list = []
            while bits:
                low = bits & -bits
                live.append(low.bit_length() - 1)
                bits ^= low
            lift = list(s.beneath) if returns else []   # from the deepest value to spill up
            while lift and lift[0] != I32 and lift[0] != I64:
                lift.pop(0)
            if returns and s.crossing:
                raise Unsupported(f"function {self.index}: a block keeps a value on the stack across the call at {s.offset}")
            if not live and not lift:
                continue
            # the frame: each value at an offset as wide as its type, i64 first; every byte written
            values: list = []                  # (local, type) for live locals, (-1 - k, type) for lift[k]
            for want in (I64, I32):
                for x in live:
                    if self.ltypes[x] == want:
                        values.append((x, want))
                for k in range(len(lift)):
                    if lift[k] == want:
                        values.append((-1 - k, want))
            offsets: list = []
            off = 0
            for _, t in values:
                offsets.append(off)
                off += 8 if t == I64 else 4
            size = (off + 15) // 16 * 16
            pre = bytearray()
            used: dict = {}
            held: list = []
            lifted: list = []
            if lift:                           # the arguments and the values to spill off the stack
                for t in reversed(s.args):
                    x = temp(t, used.get(t, 0))
                    used[t] = used.get(t, 0) + 1
                    pre.append(0x21)
                    put_uleb(pre, x)
                    held.append(x)
                for t in reversed(lift):
                    if t == V128 or t == ANY:
                        raise Unsupported(f"function {self.index}: a value of type {t} under a call's arguments")
                    x = temp(t, used.get(t, 0))
                    used[t] = used.get(t, 0) + 1
                    pre.append(0x21)
                    put_uleb(pre, x)
                    lifted.append(x)
                lifted.reverse()               # (lifted[k] holds lift[k])
            pre.append(0x23)                   # frame = __stack_pointer -= size
            put_uleb(pre, self.sp)
            pre.append(0x41)
            put_sleb(pre, size)
            pre.append(0x6B)
            pre.append(0x22)
            put_uleb(pre, frame)
            pre.append(0x24)
            put_uleb(pre, self.sp)
            for j in range(len(values)):
                x, t = values[j]
                store(pre, frame, x if x >= 0 else lifted[-1 - x], t, offsets[j])
            for pad in range(off, size, 4):
                store(pre, frame, -1, I32, pad)
            for x in lifted:                   # back on the stack as they were
                pre.append(0x20)
                put_uleb(pre, x)
            for x in reversed(held):
                pre.append(0x20)
                put_uleb(pre, x)
            post = bytearray([0x20])           # __stack_pointer = frame + size (an exception skips this:
            put_uleb(post, frame)              # the function that catches it restores the pointer)
            post.append(0x41)
            put_sleb(post, size)
            post.append(0x6A)
            post.append(0x24)
            put_uleb(post, self.sp)
            inserts.append((s.offset, 1, pre))
            inserts.append((s.end, 0, post))
        if not inserts:
            return self.body
        inserts.sort(key=lambda e: (e[0], e[1]))
        out = bytearray()
        groups = list(self.groups)
        for t in extra:
            if len(groups) > len(self.groups) and groups[-1][1] == t:
                groups[-1] = (groups[-1][0] + 1, t)
            else:
                groups.append((1, t))
        put_uleb(out, len(groups))
        for k, t in groups:
            put_uleb(out, k)
            out.append(t)
        last = self.code_start
        for at, _, code in inserts:
            out.extend(self.body[last:at])
            out.extend(code)
            last = at
        out.extend(self.body[last:])
        return bytes(out)


def store(code: bytearray, frame: int, x: int, t: int, offset: int) -> None:
    """frame[offset] = local x, or zero if x < 0, as a t (i32 or i64)"""
    code.append(0x20)
    put_uleb(code, frame)
    if x >= 0:
        code.append(0x20)
        put_uleb(code, x)
    else:
        code.append(0x41 if t == I32 else 0x42)
        code.append(0)
    code.append(0x36 if t == I32 else 0x37)
    code.append(2 if t == I32 else 3)
    put_uleb(code, offset)


# ---------- the whole module ----------

def collectors(m: Module, funcs: list) -> tuple:
    """Per function index: whether a call to it may collect (c_any), and whether it may collect and
    then return normally (c_ret). The code after a call whose callee collects only on its way to
    an exception or to exit, as pys_fail does, never runs once a collection has, so what that code
    reads need not be on the stack: only what a catch reads."""
    nimp = len(m.func_imports)
    n = len(m.func_types)
    c_any = [False] * n
    c_ret = [False] * n
    for i in range(nimp):
        c_any[i] = c_ret[i] = m.func_imports[i] not in WASI_MODULES
    seeds = [i for i in range(nimp, n) if m.func_names.get(i) == COLLECTOR]
    if len(seeds) != 1:
        raise Unsupported(f"{len(seeds)} functions named {COLLECTOR} (the name section must name exactly one)")
    c_any[seeds[0]] = c_ret[seeds[0]] = True
    callers: list = [[] for _ in range(n)]
    work: list = []
    for f in funcs:
        for s in f.sites:
            if s.callee >= 0:
                callers[s.callee].append(f.index)
            elif not c_any[f.index]:
                c_any[f.index] = True
                work.append(f.index)
    work.extend(i for i in range(n) if c_any[i] and i not in work)
    while work:
        i = work.pop()
        for c in callers[i]:
            if not c_any[c]:
                c_any[c] = True
                work.append(c)
    # c_ret: the least fixed point; each call tells whether a return follows it, and a catch's return
    calls: dict = {}
    for f in funcs:
        reach = f.reaches_return()
        calls[f.index] = [(s.callee, reach[s.nxt], any(reach[h] for h in f.succ[s.block] if h != s.nxt))
                          for s in f.sites]
    work = [f.index for f in funcs]
    while work:
        i = work.pop()
        if c_ret[i]:
            continue
        for callee, normal, caught in calls[i]:
            if (normal and (callee < 0 or c_ret[callee])) or (caught and (callee < 0 or c_any[callee])):
                c_ret[i] = True
                work.extend(callers[i])
                break
    return c_ret, c_any


def bodies_and_stack(m: Module) -> tuple:
    # the code section's function bodies, and the index of the global the name section calls __stack_pointer
    code = [pay for sid, pay in m.sections if sid == 10]
    if len(code) != 1:
        raise Unsupported("no code section")
    bodies: list = []
    n, p = uleb(code[0], 0)
    for _ in range(n):
        size, p = uleb(code[0], p)
        bodies.append(code[0][p:p + size])
        p += size
    sps = [i for i in m.global_names if m.global_names[i] == "__stack_pointer"]
    if len(sps) != 1:
        raise Unsupported("the name section does not name __stack_pointer")
    return bodies, sps[0]


def returning_collectors(data: bytes) -> dict:
    """{name: whether a call to it may collect and then return normally} for each function the
    module's name section names (wasm/check_no_collect.py)."""
    m = Module(data)
    bodies, sp = bodies_and_stack(m)
    nimp = len(m.func_imports)
    funcs: list = []
    for k in range(len(bodies)):
        f = Function(m, nimp + k, bodies[k], sp)
        f.walk()
        funcs.append(f)
    c_ret, _ = collectors(m, funcs)
    return {m.func_names[i]: c_ret[i] for i in m.func_names}


def rewrite(data: bytes, spill: bool = True) -> bytes:
    m = Module(data)
    bodies, sp = bodies_and_stack(m)
    nimp = len(m.func_imports)
    flags = [i for i in range(nimp, len(m.func_types)) if m.func_names.get(i) == FLAG]
    if len(flags) != 1 or m.types[m.func_types[flags[0]]] != ([], [I32]):
        raise Unsupported(f"no function {FLAG}() returning i32")
    funcs: list = []
    if spill:
        for k in range(len(bodies)):
            f = Function(m, nimp + k, bodies[k], sp)
            f.walk()
            funcs.append(f)
        c_ret, c_any = collectors(m, funcs)
    out_code = bytearray()
    put_uleb(out_code, len(bodies))
    for k in range(len(bodies)):
        if nimp + k == flags[0]:
            nb = b"\x00\x41\x01\x0b"           # no locals; i32.const 1; end
        elif not spill:
            nb = bodies[k]
        else:
            nb = funcs[k].rewrite(c_ret, c_any)
        put_uleb(out_code, len(nb))
        out_code.extend(nb)
    out = bytearray(data[:8])
    for sid, pay in m.sections:
        if sid == 10:
            pay = bytes(out_code)
        out.append(sid)
        put_uleb(out, len(pay))
        out.extend(pay)
    return bytes(out)


def main() -> None:
    args = sys.argv[1:]
    spill = not args or args[0] != "--no-spill"
    if not spill:
        args = args[1:]
    if len(args) != 2:
        sys.stderr.write("usage: python3 wasm/spill_roots.py [--no-spill] IN.wasm OUT.wasm\n")
        sys.exit(2)
    f = open(args[0], "rb")
    data = f.read()
    f.close()
    try:
        out = rewrite(data, spill)
    except Unsupported as e:
        sys.stderr.write(f"spill_roots: {args[0]}: {e}\n")
        sys.exit(1)
    f = open(args[1], "wb")
    f.write(out)
    f.close()


if __name__ == "__main__":
    main()
