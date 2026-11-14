# error: module 'importlib.metadata' has no attribute 'files'
import importlib.metadata

print(importlib.metadata.files("demo-pkg"))
