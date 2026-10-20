# error: class emods.dataclass_retyped.Retyped is not supported: field 'x' of 'Point' declared again in 'Retyped' with another type (not supported)
from emods.dataclass_retyped import Point, Retyped

print(Point(1))
print(Retyped())
