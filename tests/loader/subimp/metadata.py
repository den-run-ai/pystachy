# A stand-in for importlib.metadata's version(), whose PackageNotFoundError derives from
# ModuleNotFoundError (tests/programs/optional/optional_subclass_version.py)
class PackageNotFoundError(ModuleNotFoundError):
    pass


def version(name: str) -> str:
    if name != "present":
        raise PackageNotFoundError(name)
    return "1.2.3"
