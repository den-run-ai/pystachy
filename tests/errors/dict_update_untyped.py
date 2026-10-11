# error: cannot infer the type of 'd', an empty dict so far: annotate it (d: dict[K, V] = {})
# update() takes keyword arguments, but they do not give d's type here
d = {}
d.update(a=1)
print(d)
