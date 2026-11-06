class E(ValueError):
    pass


E.__module__ = "pkg"
print(E.__module__)
