# error: Constant.__init__() got an unexpected keyword argument 'lineno'
import _ast
_ast.Constant(1, lineno=1)
