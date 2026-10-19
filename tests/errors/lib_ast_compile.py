# error: unsupported call compile(str,str,str,int)
import _ast
compile("1 + 2", "<test>", "eval", _ast.PyCF_ONLY_AST)
