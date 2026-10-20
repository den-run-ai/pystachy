# purge() may run in a replacement callback. An active operation keeps its decoded input,
# and Match objects and compiled patterns remain usable after the caches are emptied.
import re

saved: list[re.Match] = []


def replacement(m: re.Match) -> str:
    re.purge()
    inner = re.search("(Ω)", "xΩy")
    assert inner is not None
    re.purge()
    ascii_match = re.search("(b)", "abc")
    assert ascii_match is not None
    re.purge()
    assert inner.group(1) == "Ω"
    assert ascii_match.group(1) == "b"
    saved.append(m)
    return "<" + str(m.group(0)) + ">"


pattern = re.compile("[a-zé]")
print(pattern.sub(replacement, "a1b2a"))
print(pattern.subn(replacement, "é1a2é"))
re.purge()
print([m.group(0) for m in saved])
print([m.expand(r"[\g<0>]") for m in saved])
print(pattern.findall("éa"))


def empty_replacement(m: re.Match) -> str:
    re.purge()
    return "-"


print(re.sub("", empty_replacement, "ab"))
print(re.sub("", empty_replacement, "éΩ"))
