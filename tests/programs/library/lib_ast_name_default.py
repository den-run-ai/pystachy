# CPython 3.13 supplies a shared Load for an omitted context, not for explicit None.
import _ast as ast

first = ast.Name("first")
second = ast.Name(id="second")
explicit = ast.Load()
third = ast.Name("third", explicit)
null = ast.Name("null", None)
stored = ast.Name("stored", ast.Store())
print(isinstance(first.ctx, ast.Load), isinstance(second.ctx, ast.Load))
print(first.ctx is second.ctx, third.ctx is explicit, third.ctx is first.ctx)
print(null.ctx is None, isinstance(stored.ctx, ast.Store))
first.ctx = ast.Store()
print(isinstance(first.ctx, ast.Store), isinstance(second.ctx, ast.Load))
first.ctx = None
print(first.ctx is None, isinstance(ast.Name("later").ctx, ast.Load))
