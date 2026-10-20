# error: cannot iterate over tuple[int,str]: its items have different types
for x in (1, "a"):
    print(x)
