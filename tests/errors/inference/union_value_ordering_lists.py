# error: recursive value ordering requires narrowing with isinstance() first
# Two values that may both be lists of the union's values: their ordering compares items of
# the union in turn, which is not compiled. One operand of a number's or a str's type is.
import json

print(json.loads("[1]") < json.loads("[2]"))
