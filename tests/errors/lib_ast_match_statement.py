# error: 'match' statements are not supported
# __match_args__ metadata does not imply that Pystachy executes class patterns.
import _ast as ast

value = ast.BinOp(ast.Name("x"), ast.Add(), ast.Constant(3))
match value:
    case ast.BinOp(ast.Name(name), ast.Add(), ast.Constant(number)):
        print(name, number)
    case _:
        print("other")
