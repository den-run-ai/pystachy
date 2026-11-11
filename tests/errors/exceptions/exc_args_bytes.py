# error: exception argument cannot be retained: a bytes value cannot become an Any value
# pystachy: dynamic-any
e = ValueError(b"bytes")
print(e.args)
