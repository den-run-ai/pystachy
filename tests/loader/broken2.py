try:
    import loader.helper
except ImportError:
    pass
print("broken2 loaded")
raise ImportError("broken2 fails")
