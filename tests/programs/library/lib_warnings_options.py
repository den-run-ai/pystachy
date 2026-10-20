# warnings reads sys.warnoptions as it is imported (CPython's -W options): each option makes a
# filter of its action, message, category, module and line, in front of the others, and one that
# is invalid is reported on stderr and ignored (the default filters, after them, are those of
# tests/deviations/lib_warnings_location.py)
import sys

sys.warnoptions.append("error::DeprecationWarning")
sys.warnoptions.append("ignore:Quiet")
sys.warnoptions.append("always::UserWarning::0")
sys.warnoptions.append("i::builtins.RuntimeWarning")
sys.warnoptions.append("once:hello:SyntaxWarning:mod:12")
sys.warnoptions.append("d::Warning:a.b")
sys.warnoptions.append("bogus")
sys.warnoptions.append("default::NoSuchWarning")
sys.warnoptions.append("ignore::pkg.Category")
sys.warnoptions.append("error::Warning::-1")
sys.warnoptions.append("error::Warning::x")
sys.warnoptions.append("a:b:c:d:e:f")
import warnings

print(len(warnings.filters))
for action, message, category, module, lineno in warnings.filters[:6]:
    m = "-" if message is None else message.pattern
    print(action, m, category.__name__, "-" if module is None else module.pattern, lineno)
with warnings.catch_warnings(record=True) as log:
    warnings.warn("quiet here", UserWarning)
    warnings.warn("hello", SyntaxWarning)
    warnings.warn("ok", RuntimeWarning)
    print(len(log), [str(m.message) for m in log])
try:
    warnings.warn("old", DeprecationWarning)
except DeprecationWarning as e:
    print("error", repr(e))
