# Python code that replaces sys.stdout (contextlib.redirect_stdout) captures Pystachy's print() too,
# as one sys.stdout would; sys.stdout = None makes print() do nothing
from pyobj import import_module, of_str

io = import_module("io")
buf = io.attr("StringIO").call([])
ctx = import_module("contextlib").attr("redirect_stdout").call([buf])
print("before")
ctx.attr("__enter__").call([])
print("captured line")
import_module("builtins").attr("print").call([of_str("python's line")])
none = import_module("builtins").attr("None")
ctx.attr("__exit__").call([none, none, none])
print("after:", repr(str(buf.attr("getvalue").call([]))))
sys = import_module("sys")
out = sys.attr("stdout")
sys.attr("__setattr__").call([of_str("stdout"), none])
print("not printed")
sys.attr("__setattr__").call([of_str("stdout"), out])
print("end")
