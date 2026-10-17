# Pystachy has no runtime extension loader, frozen code objects, or builtin registry.
import _imp


def source_candidates(paths: list[str]) -> list[str]:
    # A small module-discovery consumer can keep its capability check and lock
    # while importing the selected Python modules statically elsewhere.
    _imp.acquire_lock()
    try:
        suffixes = [".py"] + _imp.extension_suffixes()
        selected: list[str] = []
        for path in paths:
            for suffix in suffixes:
                if path.endswith(suffix):
                    selected.append(path)
                    break
        return selected
    finally:
        _imp.release_lock()


print(source_candidates(["consumer.py", "native.so", "readme.txt"]))
print("unlocked", not _imp.lock_held())
suffixes = _imp.extension_suffixes()
suffixes.append(".fake")
print("fresh suffixes", _imp.extension_suffixes())
names = _imp._frozen_module_names()
names.append("fake")
print("fresh frozen names", _imp._frozen_module_names())
print("no frozen importlib", _imp.is_frozen("_frozen_importlib"))
print("no frozen data", _imp.find_frozen("_frozen_importlib", withdata=True))

try:
    _imp.is_builtin("sys")
except NotImplementedError as error:
    print(str(error))
try:
    _imp.get_frozen_object("provided", b"not bytecode")
except NotImplementedError as error:
    print(str(error))
try:
    _imp.create_builtin("sys")
except NotImplementedError as error:
    print(str(error))
try:
    _imp.exec_builtin("sys")
except NotImplementedError as error:
    print(str(error))
try:
    _imp.create_dynamic("native", None)
except NotImplementedError as error:
    print(str(error))
try:
    _imp.exec_dynamic("native")
except NotImplementedError as error:
    print(str(error))
