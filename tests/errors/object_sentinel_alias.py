# error: unsupported call object()
# The compiler loads object()'s class where a module calls the name object: a module that calls it
# only through a variable that holds it is rejected, as on main. It works where the module also
# calls object().
obj = object
x = obj()
print(x is x)
