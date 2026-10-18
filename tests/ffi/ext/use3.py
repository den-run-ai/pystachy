import viajson
# Python -> Pystachy (total) -> Python (viajson.twice via import_module) -> Pystachy (twice): nested entries
# (the probe checks separately that the extension, not the source, is what loads)
print(viajson.total("viajson", "twice", 3000))
print(sum(2 * i for i in range(3000)))
