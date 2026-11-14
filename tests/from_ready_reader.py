from from_ready_source import EarlyClass, early_fn, early_value

print("early", EarlyClass.value, early_fn(), early_value)

try:
    from from_ready_source import LateClass as ImportedClass
    print("class imported")
except ImportError:
    print("class missing")
try:
    from from_ready_source import late_fn as imported_fn
    print("function imported")
except ImportError:
    print("function missing")
try:
    from from_ready_source import late_value as imported_value
    print("global imported", imported_value)
except ImportError:
    print("global missing")


def local_import() -> int:
    from from_ready_source import LateClass
    from from_ready_source import late_fn
    from from_ready_source import late_value
    return LateClass.value + late_fn() + late_value


try:
    print("local", local_import())
except ImportError:
    print("local missing")
print("reader done")
