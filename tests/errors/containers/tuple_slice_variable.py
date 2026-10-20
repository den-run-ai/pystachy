# error: slicing a tuple[int,str,float] by bounds or a step other than integer literals is not supported
# (a bound known only at run time would leave the slice's item types unknown)
t = (1, "a", 2.5)
n = 1
print(t[n:])
