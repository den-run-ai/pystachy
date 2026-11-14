import from_deleted_source


def read_deleted() -> int:
    from from_deleted_source import value
    return value


try:
    print("unexpected value", read_deleted())
except ImportError:
    print("deleted value missing")
