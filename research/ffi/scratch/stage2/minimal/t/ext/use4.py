import sys, io, contextlib
import fastmath as m
assert m.__file__.endswith(".so")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    m.hello("redirected")
print("captured:", repr(buf.getvalue()))
class Evil:
    def write(self, s):
        m.ncalls()
        return len(s)
    def flush(self): pass
old = sys.stdout
sys.stdout = Evil()
m.hello("evil")
sys.stdout = old
print("survived")
