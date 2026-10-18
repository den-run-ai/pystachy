# error: expected operator, got Load
import _ast
_ast.BinOp(_ast.Constant(1), _ast.Load(), _ast.Constant(2))
