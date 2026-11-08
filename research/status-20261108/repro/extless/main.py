try:
    import plainname  # noqa: F401
    print("imported")
except ImportError:
    print("fallback")
