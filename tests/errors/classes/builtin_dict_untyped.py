# error: cannot infer what 'Made' objects hold before an item is stored in one: name it in the base (class Made(dict[K, V]))
class Made(dict):
    pass


m = Made()
print(m)
