# A parameter typed str | bytes | None (ast_serialize.parse()'s source, as the extension's stub
# types it): rejected with "bytes in a closed union is not supported"; the port leaves it
# unannotated, so each call specializes it
def size(source: str | bytes | None = None) -> int:
    if source is None:
        return 0
    if isinstance(source, str):
        return len(source.encode())
    return len(source)


print(size("ab"), size(b"abc"), size())
