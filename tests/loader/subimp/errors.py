# ImportError subclasses for the optional imports of tests/programs/optional/optional_subclass_*
class Missing(ImportError):
    pass


def require(name: str, have: bool) -> str:
    if not have:
        raise Missing(f"{name} is not installed")
    return name
