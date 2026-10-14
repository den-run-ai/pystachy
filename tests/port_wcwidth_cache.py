# Upstream wcwidth 0.9.2's cache contract, including calls with defaults and keywords.
from wcwidth import _wcmatch_version, wcwidth, wcswidth

wcwidth.cache_clear()
assert wcwidth.cache_info() == (0, 0, 1024, 0)
assert wcwidth("\u00a1") == 1
assert wcwidth("\u00a1") == 1
assert wcwidth("\u00a1", ambiguous_width=2) == 2
assert wcwidth("\u00a1", ambiguous_width=2) == 2
assert wcwidth("\u00a1", "auto", 1) == 1
assert wcwidth.cache_info() == (2, 3, 1024, 3)
assert wcwidth.__wrapped__("\u00a1", "auto", 2) == 2
assert wcwidth.cache_info() == (2, 3, 1024, 3)

# Errors count as misses without inserting a result.
for i in range(2):
    try:
        wcwidth("ab")
        assert False
    except TypeError:
        pass
assert wcwidth.cache_info() == (2, 5, 1024, 3)

# Fill beyond capacity, then confirm the old character has been evicted.
for cp in range(0x1000, 0x1400):
    wcwidth("%c" % cp)
assert wcwidth.cache_info().currsize == 1024
misses = wcwidth.cache_info().misses
assert wcwidth("\u00a1") == 1
assert wcwidth.cache_info().misses == misses + 1
assert wcwidth("\u00a1") == 1
assert wcwidth.cache_info().misses == misses + 1
wcwidth.cache_clear()
assert wcwidth.cache_info() == (0, 0, 1024, 0)

# The string-width implementation preserves Unicode graphemes and ASCII fast paths.
assert wcswidth("plain ASCII") == 11
assert wcswidth("\u4e2d\u00e9\u0301") == 3
assert wcswidth("\u00a1", ambiguous_width=2) == 2
assert wcswidth("\U0001f469\U0001f3fd\u200d\U0001f4bb") == 2

_wcmatch_version.cache_clear()
assert _wcmatch_version("auto") == _wcmatch_version("auto")
assert _wcmatch_version.cache_info() == (1, 1, 8, 1)
_wcmatch_version.cache_clear()
assert _wcmatch_version.cache_info() == (0, 0, 8, 0)
print("wcwidth cache checks passed")
