"""Turn `pystachy ir` output into a library module (what a driver `--lib`/`ext` mode would emit).

usage: libify.py IN.ll OUT.ll MODE   (MODE: naive | eh)
  naive: @main replaced by @pyx_init (pys_init + pys_eh_on + @main.init); each @f.NAME gets an
         exported C-ABI wrapper @pyx_NAME that just calls it (no exception boundary).
  eh:    as naive, but each wrapper is a boundary: invoke + `landingpad catch ptr null` under
         pys_personality, returning the Exc* through an extra out-parameter (zero cost until a raise).
"""
import re
import sys

src, dst, mode = sys.argv[1], sys.argv[2], sys.argv[3]
ir = open(src, encoding="latin-1").read()

# 1. drop @main (keep everything else, incl. @pys.roots and @main.init)
m = re.search(r"^define i32 @main\(i32 %argc, ptr %argv\) \{\n(.*?)^\}\n", ir, re.S | re.M)
body = m.group(1)
nroots = re.search(r"ptr @pys.roots, i64 (\d+)\)", body).group(1)
has_eh = "@pys_eh_on" in body
ir = ir[: m.start()] + ir[m.end() :]

out = [ir]
decl = set(re.findall(r"^declare [^@]*@([\w.]+)\(", ir, re.M))


def need(d: str, name: str) -> None:
    if name not in decl:
        out.append(d)
        decl.add(name)


need("declare void @pys_eh_on()", "pys_eh_on")
need("declare ptr @llvm.frameaddress.p0(i32)", "llvm.frameaddress.p0")
need("declare i32 @pys_personality(i32, i32, i64, ptr, ptr)", "pys_personality")
need("declare i64 @pys_try_mark()", "pys_try_mark")
need("declare ptr @pys_exc_handled()", "pys_exc_handled")
need("declare ptr @pys_exc_begin(ptr, i64)", "pys_exc_begin")
need("declare void @pys_exc_restore(ptr)", "pys_exc_restore")
init_fn = "pys_init_lib" if mode == "eh" else "pys_init"
if mode == "eh":
    need("declare void @pys_init_lib(ptr, ptr, i64)", "pys_init_lib")
    init_call = f"  call void @pys_init_lib(ptr %sb, ptr @pys.roots, i64 {nroots})"
else:
    init_call = f"  call void @pys_init(i32 0, ptr null, ptr %sb, ptr @pys.roots, i64 {nroots})"

# 2. the module's init: the runtime, exceptions always on (a library has a boundary), then module code
out.append(
    "define void @pyx_init() {\n"
    "  %sb = call ptr @llvm.frameaddress.p0(i32 0)\n"
    f"{init_call}\n"
    "  call void @pys_eh_on()\n"
    "  call void @main.init()\n"
    "  ret void\n"
    "}"
)

# 3. one exported wrapper per module-level function
for ret, name, params in re.findall(r"^define internal (\S+) @f\.(\w+)\(([^)]*)\)", ir, re.M):
    ps = [p.strip() for p in params.split(",") if p.strip()]
    tys = [p.split()[0] for p in ps]
    args = ", ".join(f"{t} %p{i}" for i, t in enumerate(tys))
    call_args = args
    if mode == "naive":
        r = "" if ret == "void" else "%r = "
        out.append(
            f"define {ret} @pyx_{name}({args}) {{\n"
            f"  {r}call {ret} @f.{name}({call_args})\n"
            f"  ret {ret} {'%r' if ret != 'void' else ''}\n".replace("ret void \n", "ret void\n")
            + "}"
        )
        continue
    sig = args + (", " if args else "") + "ptr %err"
    r = "" if ret == "void" else "%r = "
    zero = "" if ret == "void" else (" 0" if ret == "i64" else " null" if ret == "ptr" else " 0.0")
    out.append(
        f"define {ret} @pyx_{name}({sig}) personality ptr @pys_personality {{\n"
        "entry:\n"
        "  %mark = call i64 @pys_try_mark()\n"
        "  %prev = call ptr @pys_exc_handled()\n"
        f"  {r}invoke {ret} @f.{name}({call_args}) to label %ok unwind label %lp\n"
        "ok:\n"
        f"  ret {ret}{' %r' if ret != 'void' else ''}\n"
        "lp:\n"
        "  %x = landingpad { ptr, i32 } catch ptr null\n"
        "  %ue = extractvalue { ptr, i32 } %x, 0\n"
        "  %e = call ptr @pys_exc_begin(ptr %ue, i64 %mark)\n"
        "  call void @pys_exc_restore(ptr %prev)\n"
        "  store ptr %e, ptr %err\n"
        f"  ret {ret}{zero}\n"
        "}"
    )

open(dst, "w", encoding="latin-1").write("\n".join(out) + "\n")
print(f"{dst}: roots={nroots} program_eh={has_eh} mode={mode}")
