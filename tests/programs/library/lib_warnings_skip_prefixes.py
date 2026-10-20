# warn() checks each of skip_file_prefixes, as CPython's C warn() does: a member that is not a
# str raises TypeError, after the check of the category and wherever the call is. (A tuple of
# a str and another type is a compile-time error: tests/errors/library/lib_warnings_skip_prefixes_mixed.py)
import warnings


def call() -> None:
    warnings.warn("in a function", skip_file_prefixes=(1,))


try:
    warnings.warn("top", skip_file_prefixes=(1,))
except TypeError as e:
    print("top:", e)
try:
    call()
except TypeError as e:
    print("call:", e)
try:
    warnings.warn("ints", skip_file_prefixes=(1, 2))
except TypeError as e:
    print("ints:", e)
try:
    warnings.warn("bytes", skip_file_prefixes=(b"/nowhere",))
except TypeError as e:
    print("bytes:", e)
try:
    warnings.warn("category first", 5, skip_file_prefixes=(1,))
except TypeError as e:
    print("category:", e)
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("always")
    warnings.warn("str prefixes", skip_file_prefixes=("/nowhere",))
    warnings.warn("empty", skip_file_prefixes=())
print([str(w.message) for w in log])
