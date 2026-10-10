# The "hand edit" of a Pystachy-generated .ll, automated: the body of every stub
#   def py_x(...) -> T: ...
# (compiled as `define internal T @f.py_x(...)`, which raises "ended without returning a value")
# becomes a call to the C function @py_x of pyshim.c, declared with the same LLVM types.
# addr_cb_square / addr_of_list / list_at_addr are pointer casts the subset cannot spell.
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding="latin-1").read().split("\n")
out: list[str] = []
decls: list[str] = []
i = 0
pat = re.compile(r"^define internal (\S+) @f\.((?:py_|addr_|list_at_)\w*)\((.*)\) \{$")
while i < len(lines):
    m = pat.match(lines[i])
    if not m:
        out.append(lines[i])
        i += 1
        continue
    ret, name, params = m.group(1), m.group(2), m.group(3)
    while lines[i] != "}":
        i += 1
    i += 1
    ps = [p.strip() for p in params.split(",") if p.strip()]
    types = [p.split()[0] for p in ps]
    args = ", ".join(ps)
    body = []
    if name == "addr_cb_square":
        body = ["  ret i64 ptrtoint (ptr @f.cb_square to i64)"]
    elif name == "addr_of_list":
        body = ["  %r = ptrtoint ptr %a0 to i64", "  ret i64 %r"]
    elif name == "list_at_addr":
        body = ["  %r = inttoptr i64 %a0 to ptr", "  ret ptr %r"]
    else:
        decls.append(f"declare {ret} @{name}({', '.join(types)})")
        if ret == "void":
            body = [f"  call void @{name}({args})", "  ret void"]
        else:
            body = [f"  %r = call {ret} @{name}({args})", f"  ret {ret} %r"]
    out.append(f"define internal {ret} @f.{name}({params}) {{")
    out.append("entry:")
    out.extend(body)
    out.append("}")
open(dst, "w", encoding="latin-1").write("\n".join(out + decls) + "\n")
print(f"rewrote {len(decls)} stubs into calls to C shims", file=sys.stderr)
