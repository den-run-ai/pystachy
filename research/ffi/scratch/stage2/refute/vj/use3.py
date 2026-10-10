import viajson
assert viajson.__file__.endswith(".so")
# Python -> Pystachy (total) -> Python (viajson.twice via import_module) -> Pystachy (twice): nested entries
print(viajson.total("viajson", "twice", 3000))
print(sum(2 * i for i in range(3000)))
