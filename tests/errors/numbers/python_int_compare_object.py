# error: cannot compare int == Plain
# pystachy: python-int
class Plain:
    pass


x = 2 ** 70
print(x == Plain())
