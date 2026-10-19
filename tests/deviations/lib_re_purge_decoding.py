# lib/re additionally caches the last subject's decoded input (of a subject with a character of
# several bytes). purge() releases those
# references, leaving existing states intact and the cumulative decoding counter unchanged.
import re


def check(subject: str) -> None:
    pattern = re.compile(".")
    state = pattern._state(subject, 0, len(subject))
    codes = re._last_codes
    offs = re._last_offs
    expected_codes = codes.copy()
    expected_offs = offs.copy()
    decoded = re._decoded
    re.purge()
    print("released", re._last == "", len(re._last_codes), len(re._last_offs))
    print("owned", state.s is codes, state.offs is offs, codes == expected_codes, offs == expected_offs)
    print("replaced", re._last_codes is not codes, re._last_offs is not offs, re._decoded == decoded)
    # The next operation must decode this same object again; subsequent operations reuse it.
    pattern.match(subject)
    print("decoded again", re._decoded - decoded == len(codes), re._last_codes is not codes)
    decoded = re._decoded
    pattern.search(subject)
    print("reused", re._decoded == decoded)
    re.purge()
    re.purge()
    print("idempotent", re._last == "", len(re._last_codes), len(re._last_offs), re._decoded == decoded)


check("abcd" * 100 + "é")
check("éΩ" * 100)

# A subject whose bytes are its code points is read in place: it is neither decoded nor cached.
flat = "abcd" * 100
re.purge()
decoded = re._decoded
re.compile(".").match(flat)
re.compile("d").search(flat)
print("in place", re._decoded == decoded, re._last == "", len(re._last_codes))
