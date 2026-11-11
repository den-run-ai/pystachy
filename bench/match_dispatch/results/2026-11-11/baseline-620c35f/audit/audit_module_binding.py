x=8
match (1, 2):
    case (x, 0): pass
print(x)
match 3:
    case x if x == 4: pass
print(x)
