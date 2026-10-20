# Mandatory repeats can reject impossible starting positions using the first literal or class,
# including after capture marks. Do not skip nullable repeats, branches or assertions in the body.
import re


def describe(m: re.Match | None) -> str:
    if m is None:
        return "None"
    groups = [repr(m.group(i)) for i in range(m.re.groups + 1)]
    return str(m.start()) + ":" + str(m.end()) + " " + ",".join(groups)


for pattern in [
    r"([a-z][a-z0-9]*,)+",
    r"(?:[a-z][a-z0-9]*,)+",
    r"(?i:([a-z][a-z0-9]*,)+?)",
    r"(?:([a-z])([0-9]),){1,3}",
    r"(?:(a,)b,)+",
    r"(?:(a?)b,)+",
    r"(?:(?=a)a,)+",
    r"(?:(a,)|b,)+",
    r"(?:(?:a,b,)|a,)+",
    r"(?:a,)*",
    r"(?:a,)*?",
    r"(?:(a?)b,)*",
    r"((a,)+)\1",
    r"(?i:(([a-z]),)+)(?-i:A)",
]:
    rx = re.compile(pattern)
    print(pattern)
    for text in ["--a5,b7,c9,--", "--a,b,a,b,--", "--b,b,--", "--A,ſ,İ,ı,K,A--", "--", ""]:
        print([describe(m) for m in rx.finditer(text)])
    print(describe(rx.search("--a5,b7,c9,--", 3, 8)))
