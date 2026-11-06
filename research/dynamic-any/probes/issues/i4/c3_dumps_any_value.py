# pystachy: dynamic-any
import json
from typing import Any

def payload(n: int) -> Any:
    return {"n": n, "ok": n > 1, "tags": ["a"]}


print(json.dumps(payload(2)))
