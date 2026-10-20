# error: expected list[expr], got None
# A list field holds a list: CPython keeps an explicit None and rejects it only in compile()
import _ast as ast

ast.List(None)
