# error: unsupported call type(exc): type(e) of an exception is supported as type(e).__name__ (and isinstance(e, C) tests its class)
try:
    open("/nonexistent_q")
except OSError as e:
    print(type(e) is FileNotFoundError)
