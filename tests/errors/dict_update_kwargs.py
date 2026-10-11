# error: dict.update() with keyword arguments adds str keys, which a dict[int,int] cannot hold
d = {1: 1}
d.update(a=2)
