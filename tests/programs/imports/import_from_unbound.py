try:
    import from_unbound_class_source
except ImportError:
    print("class missing")
try:
    import from_unbound_function_source
except ImportError:
    print("function missing")
try:
    import from_unbound_global_source
except ImportError:
    print("global missing")
