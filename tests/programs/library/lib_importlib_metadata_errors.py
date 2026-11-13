# importlib.metadata's errors: PackageNotFoundError of a name that no directory of the module
# path has metadata for, with the name it gives, and ValueError of an empty name.
import importlib.metadata
from importlib.metadata import Distribution, PackageNotFoundError, distribution, metadata, requires, version

for name in ["does-not-exist", "p", "pkg", "pkg.", "demo", "demo-pkg-extra", "multi-part", "not-a-dist", "not", "Distinfo Pkg", " demo-pkg"]:
    try:
        print(version(name))
    except PackageNotFoundError as error:
        print(str(error), "|", error.name, "|", repr(error))
    try:
        print(requires(name))
    except PackageNotFoundError as error:
        print(error, "|", error.name)
    try:
        metadata(name)
    except ModuleNotFoundError as error:
        print(type(error).__name__, error)
    try:
        distribution(name)
    except ImportError as error:
        print(type(error).__name__, error, isinstance(error, PackageNotFoundError))
try:
    version("")
except ValueError as error:
    print(type(error).__name__, error)
try:
    requires("")
except ValueError as error:
    print(type(error).__name__, error)
try:
    metadata("")
except ValueError as error:
    print(type(error).__name__, error)
try:
    Distribution.from_name("")
except ValueError as error:
    print(error)
try:
    raise importlib.metadata.PackageNotFoundError("some-name")
except Exception as error:
    print(type(error).__name__, error)
try:
    raise PackageNotFoundError("other")
except PackageNotFoundError as error:
    print(error.name, str(error) == "No package metadata was found for other")
print(issubclass(PackageNotFoundError, ModuleNotFoundError), issubclass(PackageNotFoundError, ImportError))
print(PackageNotFoundError.__name__)
