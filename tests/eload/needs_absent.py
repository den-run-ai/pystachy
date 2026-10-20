try:
    import yaml
except ImportError:
    raise ImportError("needs_absent needs yaml")
print("needs_absent loaded")
