import sys
sys.path.insert(0, sys.argv[1])
import analyze as a
OLD, NEW = "/home/user/wt/alpha2-qual/build/ref", "/home/user/wt/alpha2-qual"
def const(name, text, ascii_=True):
    n = len(text.encode()) + 1
    esc = "".join(c if 32 <= ord(c) <= 126 and c not in '"\\' else "".join("\\%02X" % b for b in c.encode()) for c in text)
    return f'{name} = private unnamed_addr global {{i64, i64, i64, [{n} x i8]}} {{i64 {n-1}, i64 0, i64 {n if ascii_ else 0}, [{n} x i8] c"{esc}\\00"}}, align 8'
def check(label, old_lines, new_lines, expect):
    st = {"outside_constants": 0, "inconsistent_constants": 0, "unmatched_in_constants": 0, "rewritten_constants": 0, "rewritten_paths": 0}
    got = a.subst_ir("\n".join(old_lines), OLD, NEW, st) == "\n".join(new_lines)
    print(("PASS" if got == expect else "FAIL"), label, "equal" if got else "residual", st)
    return got == expect
msg = "cannot import name 'GenericAlias' from 'types' ({}/lib/types.py)"
ok = all([
  check("path-only constant", ["x", const("@s.81", msg.format(OLD)), "y"], ["x", const("@s.81", msg.format(NEW)), "y"], True),
  check("sys.prefix whole payload", [const("@s.3", OLD)], [const("@s.3", NEW)], True),
  check("two paths in one constant", [const("@s.4", f"{OLD}/lib/a.py {OLD}/lib/b.py")], [const("@s.4", f"{NEW}/lib/a.py {NEW}/lib/b.py")], True),
  check("NEG changed name", [const("@s.81", msg.format(OLD))], [const("@s.81", msg.replace("GenericAlias", "GenericAliaz").format(NEW))], False),
  check("NEG other module path", [const("@s.81", msg.format(OLD))], [const("@s.81", msg.format(NEW).replace("types.py", "typing.py"))], False),
  check("NEG unrelated path", [const("@s.9", "/elsewhere/lib/types.py")], [const("@s.9", "/elsewhere2/lib/types.py")], False),
  check("NEG prefix-only match (refx)", [const("@s.5", OLD + "x/lib")], [const("@s.5", NEW + "x/lib")], False),
  check("NEG path outside a constant", ["; " + OLD + "/lib/types.py"], ["; " + NEW + "/lib/types.py"], False),
  check("NEG wrong length field kept", [const("@s.81", msg.format(OLD))], [const("@s.81", msg.format(NEW)).replace("i64 0, i64", "i64 1, i64")], False),
  check("NEG changed IR elsewhere", [const("@s.81", msg.format(OLD)), "  %1 = add i64 1, 2"], [const("@s.81", msg.format(NEW)), "  %1 = add i64 1, 3"], False),
  check("non-ASCII constant keeps chars 0", [const("@s.6", "é " + OLD + "/lib/x.py", False)], [const("@s.6", "é " + NEW + "/lib/x.py", False)], True),
])
print("ALL PASS" if ok else "SOME FAIL")
