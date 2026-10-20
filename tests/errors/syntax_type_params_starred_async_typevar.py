# error: syntax_type_params_starred_async_typevar.py:2: error: invalid syntax
async def get[T = *int](x: T) -> T:
    return x


print("ran")
