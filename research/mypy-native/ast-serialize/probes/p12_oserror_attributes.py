# An OSError's strerror and errno: "the attributes of an exception (e.strerror) are not
# supported"; the port parses str(e) ("[Errno 2] No such file or directory: '...'")
try:
    open("/nonexistent/x.py", "rb")
except OSError as e:
    print(e.strerror, e.errno)
