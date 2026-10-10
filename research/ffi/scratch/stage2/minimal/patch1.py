import sys
p = sys.argv[1]
s = open(p, encoding="latin-1").read()
def rep(a, b, n=1):
    global s
    c = s.count(a)
    if c != n:
        raise SystemExit(f"expected {n} of {a!r}, found {c}")
    s = s.replace(a, b)

# E1 the builtin module
rep('for _k in "sys os os.path math tempfile typing dataclasses __future__ builtins time errno".split():',
    'for _k in "sys os os.path math tempfile typing dataclasses __future__ builtins time errno ffi".split():')
# E2 its names
rep('''    if mod == "dataclasses":
        return x == "dataclass"
    return mod == "builtins"''',
'''    if mod == "dataclasses":
        return x == "dataclass"
    if mod == "ffi":
        return x == "extern" or x == "string_at"
    return mod == "builtins"''')
# E4 an imported module may apply @ffi.extern("lib") (it runs no code of the program)
rep('''"typing.runtime_checkable": "c", "object.__new__": "c"}''',
    '''"typing.runtime_checkable": "c", "object.__new__": "c", "ffi.extern": "f"}''')
rep('''e = e if e != "" or len(x.kids) == 0 or key == "dataclasses.dataclass" else f"it calls {short(x.s)}()"''',
    '''e = e if e != "" or len(x.kids) == 0 or key == "dataclasses.dataclass" or key == "ffi.extern" else f"it calls {short(x.s)}()"''')
# E6 declare_fn: @ffi.extern("lib"[, "symbol"]) def f(...) -> T: ... is the C function of that name
rep('''        elif self.rtmode and cls == "" and d.s.startswith("pys_"):
            f.ll = "@" + d.s
            f.export = True
            self.rtdefs[d.s] = f
        ps = d.kids[0].kids''',
'''        elif self.rtmode and cls == "" and d.s.startswith("pys_"):
            f.ll = "@" + d.s
            f.export = True
            self.rtdefs[d.s] = f
        for x in d.kids[3:] if cls == "" and not self.rtmode else []:
            a = x.kids[0].kids[1:] if len(x.kids) > 0 else []
            if self.imported(x.s) == "ffi.extern":
                if len(a) == 0 or len(a) > 2 or a[0].kind != "str" or (len(a) == 2 and a[1].kind != "str") or len(d.kids) != 4:
                    self.err('@extern takes the library ("" for the process\\'s own) and an optional symbol name, as string literals')
                if len(body) != 1 or body[0].kind != "expr" or body[0].kids[0].kind != "ellipsis":
                    self.err(f"{short(d.s)}() is a C function (@extern): its body must be ...")
                f.extern = True
                f.lib = a[0].s
                f.csym = "@" + (a[1].s if len(a) == 2 else short(d.s))
        ps = d.kids[0].kids''')
rep('''        if deco != "" and f.deco == "" and not self.lib:''',
    '''        if deco != "" and f.deco == "" and not self.lib and not f.extern:''')
rep('''        if len(d.kids) > 3 and f.deco == "":
            bad = f"unsupported decorator''', '''        if len(d.kids) > 3 and f.deco == "" and not f.extern:
            bad = f"unsupported decorator''')
rep('''        self.extern = False  # runtime mode: a function whose body is `...`, declared under its C name and defined in C''',
    '''        self.extern = False  # runtime mode: a function whose body is `...`, declared under its C name and defined in C
        self.lib = ""  # @ffi.extern's library ("" the process's own)
        self.csym = ""  # and its C symbol''')
rep('''        if self.rtmode and (f.export or f.extern) and f.generic:''',
    '''        if (f.export or f.extern) and f.generic:''')
# E7 program(): externs first (an imported module's too); a user extern is called through an internal stub
rep('''        for f in self.funcs.values():
            if f.mod != "" and not f.generic:
                self.lazy[f.ll] = f
            elif f.extern:''',
'''        for f in self.funcs.values():
            if f.extern and not self.rtmode:
                self.cextern(f)
            elif f.mod != "" and not f.generic:
                self.lazy[f.ll] = f
            elif f.extern:''')
rep('''    def untold(self, f: FnInfo, ts: list[str], how: str) -> None:''',
'''    def cextern(self, f: FnInfo) -> None:
        # @ffi.extern: the program calls @f.<name> as any function, an internal stub that passes a
        # str as its bytes (const char *, NUL-terminated) and copies a returned char * (NULL: None)
        self.line = f.node.line
        ps: list[str] = []
        args: list[str] = []
        code: list[str] = []
        for j in range(len(f.ptypes)):
            t = f.ptypes[j]
            if t not in ("int", "float", "str"):
                self.err(f"C function {f.name}() takes {typestr(t)}: an @extern function takes int, float or str")
            ps.append(f"{lt(t)} %a{j}")
            if t == "str":
                code.append(f"  %p{j} = getelementptr i8, ptr %a{j}, i64 8")
            args.append(f"{lt(t)} %{'p' if t == 'str' else 'a'}{j}")
        if f.ret not in ("int", "float", "str", "None", "opt[str]"):
            self.err(f"C function {f.name}() returns {typestr(f.ret)}: an @extern function returns int, float, str, str | None or None")
        r = "ptr" if f.ret == "opt[str]" else lt(f.ret)
        cl = f"call {r} {f.csym}({', '.join(args)})"
        if r == "void":
            code.extend([f"  {cl}", "  ret void"])
        elif f.ret == "str" or f.ret == "opt[str]":
            self.runtime("pys_cstr")
            code.extend([f"  %r = {cl}", f"  %s = call ptr @pys_cstr(ptr %r, i64 {1 if f.ret == 'str' else 0})", "  ret ptr %s"])
        else:
            code.extend([f"  %r = {cl}", f"  ret {r} %r"])
        self.externs[f.ll] = f"declare {r} {f.csym}({', '.join([lt(t) for t in f.ptypes])})\\ndefine internal {lt(f.ret)} {f.ll}({', '.join(ps)}) {{\\n" + "\\n".join(code) + "\\n}"
        if f.lib != "" and f.lib not in LIBS:
            LIBS.append(f.lib)

    def untold(self, f: FnInfo, ts: list[str], how: str) -> None:''')
rep('''MODULES: dict[str, bool] = {}
for _k''', '''MODULES: dict[str, bool] = {}
LIBS: list[str] = []  # the libraries of the program's @ffi.extern functions (the driver links them)
for _k''')
# E9 runtime entries
rep('''"alloc_atomic": "%ptr:int|A|",''', '''"alloc_atomic": "%ptr:int|A|", "cstr": "opt[str]:%ptr,int|R A|", "string_at": "str:int,int|A|",''')
rep('''    "os.getenv(str,str)": "pys_getenv:str",''', '''    "os.getenv(str,str)": "pys_getenv:str", "ffi.string_at(int,int)": "pys_string_at:str",''')
open(p, "w", encoding="latin-1").write(s)
