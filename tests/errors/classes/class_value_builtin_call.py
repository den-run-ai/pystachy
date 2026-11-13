# error: calling a class object that may be any class's (type[object]) is not supported
# A builtin class held as any class's class object is not called: its result has no one type.
registry: dict[str, type] = {"i": int, "s": str}
print(registry["i"]("42"))
