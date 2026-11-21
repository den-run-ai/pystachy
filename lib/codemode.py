"""Call synchronous tools supplied by a Pystachy WebAssembly host."""


def call(name: str, payload: str) -> str:
    """Pass a Unicode string to a named host tool and return its Unicode response."""
    return __pys_tool_call(name, payload)
