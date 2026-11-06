# pystachy: dynamic-any
import json
from typing import Any

rec: dict[str, Any] = {"name": "x", "n": 3}
print(json.dumps(rec))
