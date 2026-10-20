# error: a generator expression that reads 'x', a variable of a comprehension around it, is not supported (it would read the variable's last value when it runs)
gens = [(x * y for y in range(2)) for x in range(3)]
print([list(g) for g in gens])
