# error: keyword.__init__() missing 1 required positional argument: 'arg'
# CPython 3.13 defaults arg to None before the required value; the typed constructor takes both
import _ast as ast

ast.keyword(value=ast.Constant(1))
