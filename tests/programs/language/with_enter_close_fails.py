# If a later __enter__ fails, previously entered files close, and close failure takes precedence.
f = open("/dev/full", "w")
f.write("lost")
with f, open("/dev/null/missing") as g:
    print("unreachable")
