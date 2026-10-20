# error: expected bool | float | int | str | None, got bytes
import _ast
_ast.Constant(b"bytes")
