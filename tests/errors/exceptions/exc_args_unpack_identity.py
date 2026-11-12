# error: retaining a sole unpacked exception tuple is not supported: pass its items explicitly
# pystachy: dynamic-any
args = (1, "message")
e = ValueError(*args)
print(e.args is args)
