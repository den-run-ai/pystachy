# %c of an empty str raises CPython's TypeError
s = ""
print("before")
print("[%c]" % s)
