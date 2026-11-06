# pystachy: dynamic-any
# json.loads into Any storage, then generic access
import json
from typing import Any

doc: Any = json.loads('{"a": [1, "two", {"b": null}], "n": 2.5}')
print(doc["a"][1], doc["n"] * 2, doc["a"][2]["b"])
