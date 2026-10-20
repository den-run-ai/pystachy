# error: syntax_type_params_starred_async_paramspec.py:3: error: invalid syntax
def outer(x):
    async def hook[**P = *int]() -> None:
        pass

    return x


print("ran")
