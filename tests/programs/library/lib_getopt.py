# lib/getopt.py: CPython 3.13's getopt with its marked edits (lib/README.md), against CPython's
# own. Cases after CPython's Lib/test/test_getopt.py.
import getopt
from getopt import GetoptError, gnu_getopt


def show(args: list[str], shortopts: str, longopts: list[str]) -> None:
    try:
        opts, rest = getopt.getopt(args, shortopts, longopts)
        print("getopt", opts, rest)
    except GetoptError as e:
        print("getopt error:", e, "|", e.msg, "|", e.opt)
    try:
        opts, rest = gnu_getopt(args, shortopts, longopts)
        print("gnu   ", opts, rest)
    except GetoptError as e:
        print("gnu    error:", e, "|", e.msg, "|", e.opt)


# short options: flags, an argument attached or next, flags joined, '-' and '--'
show(["-a", "-b", "1", "--alpha=2", "--beta", "-a", "3", "-a", "", "--beta", "arg1", "arg2"], "a:b", ["alpha=", "beta"])
show(["-ab", "-cvalue", "-c", "next", "x"], "abc:", [])
show(["-abcfoo", "rest"], "abc:", [])
show(["-", "-a", "x"], "a", [])
show(["-a", "--", "-b", "x"], "ab", [])
show(["x", "-a", "y", "--alpha", "z"], "a", ["alpha"])
show(["-a", "-1", "-b"], "a:b", [])
show([], "ab", ["alpha"])
show(["--", "--"], "a", [])

# long options: exact, = values, values from the next argument, unique prefixes, -- as a value
show(["--alpha", "1", "--beta=", "--gamma"], "", ["alpha=", "beta=", "gamma"])
show(["--alp=v", "--gam"], "", ["alpha=", "gamma"])
show(["--abc=1", "--abcd"], "", ["abcd=", "abcde"])
show(["--python", "foo"], "", ["python", "pythonista"])
show(["--py", "x"], "", ["python", "pythonista"])
show(["--abc=--"], "", ["abc="])
show(["--a=b=c"], "", ["a="])

# errors: not recognized, a missing argument, an argument where none is taken, an ambiguous prefix
show(["-x"], "ab:", [])
show(["-b"], "ab:", [])
show(["--alpha"], "", ["alpha="])
show(["--beta=1"], "", ["beta"])
show(["--al"], "", ["alpha", "alps"])
show(["--zeta"], "", ["alpha"])
show(["-a", "x", "-z"], "a", [])
show(["--"], "", [])

# gnu_getopt: '+' first in the short options stops at the first non-option argument
for argv in [["-a", "x", "-b"], ["x", "-a"], ["-a", "--", "-b"]]:
    try:
        print("gnu + ", gnu_getopt(argv, "+ab", []))
    except GetoptError as e:
        print("gnu + error:", e)

# the helpers the functions use
print(getopt.short_has_arg("a", "a:"), getopt.short_has_arg("a", "a"), getopt.short_has_arg("a", "ba:"))
for opt, longs in [("abc", ["abc="]), ("abc", ["abc"]), ("abc", ["abcd"]), ("abc", ["def"]), ("abc", ["abcd", "abcde"])]:
    try:
        print(getopt.long_has_args(opt, longs))
    except GetoptError as e:
        print("error:", e)
empty: list[tuple[str, str]] = []
none: list[str] = []
print(getopt.do_shorts(empty, "a", "a", none), getopt.do_shorts([("-z", "")], "a1", "a:", none))
print(getopt.do_shorts([("-z", "")], "a", "a:", ["1", "2"]))
print(getopt.do_longs([("-z", "")], "abc=1", ["abcd="], ["x"]), getopt.do_longs([("-z", "")], "abc", ["ab", "abc", "abcd"], none))
try:
    getopt.do_shorts([("-z", "")], "a1", "a", none)
except GetoptError as e:
    print("error:", e, e.opt)

e = GetoptError("message", "opt")
print(str(e), e.msg, e.opt, GetoptError("only").opt == "")
try:
    getopt.getopt(["-q"], "")
except getopt.error as err:  # (the old name of GetoptError)
    print("getopt.error:", err)
print(isinstance(e, Exception), repr(e))
