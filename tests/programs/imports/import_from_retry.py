try:
    import from_retry_class_source
except ValueError:
    print("class first failed")
try:
    import from_retry_class_source
except ImportError:
    print("class second missing")
try:
    import from_retry_function_source
except ValueError:
    print("function first failed")
try:
    import from_retry_function_source
except ImportError:
    print("function second missing")
try:
    import from_retry_global_source
except ValueError:
    print("global first failed")
try:
    import from_retry_global_source
except ImportError:
    print("global second missing")
