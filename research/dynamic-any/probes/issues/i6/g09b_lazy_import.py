def fmt(s: str) -> str:
    import textwrap
    return textwrap.dedent(s)


print(fmt("  a"))
