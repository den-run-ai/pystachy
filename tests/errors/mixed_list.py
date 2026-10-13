# error: expected int, got <built-in function len>
# a list whose items have types that nothing holds together (a union holds no functions; a
# list of an int and a str is a list[int | str])
xs = [1, len]
