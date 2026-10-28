# pystachy: dynamic-any
# Pystachy port: in-memory, schema-free entry points only.
from .json_repair import loads, repair_json

__all__ = ["loads", "repair_json"]
