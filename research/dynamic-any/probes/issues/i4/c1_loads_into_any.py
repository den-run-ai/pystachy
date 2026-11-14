# pystachy: dynamic-any
import json
from typing import Any

doc: Any = json.loads('{"a": [1, "two", {"b": null}], "n": 2.5}')
print(doc["a"][1], doc["n"] * 2)
