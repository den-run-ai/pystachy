from typing import TypedDict
class ErrorInfo(TypedDict):
    line: int
    message: str
e: ErrorInfo = {"line": 1, "message": "m"}
print(e["message"], e["line"])
