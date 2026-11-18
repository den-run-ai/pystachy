# A package whose code imports its own submodule, whose import of a missing module fails.
print("selfpkg: start")
from .child import thing
print("selfpkg: not reached", thing)
