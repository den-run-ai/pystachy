# error: class emods.dataclass_retyped.Below is not supported: its base emods.dataclass_retyped.Retyped is not supported: field 'x' of 'Point' declared again in 'Retyped' with another type (not supported)
from emods import dataclass_retyped

print(dataclass_retyped.Point(1))
print(dataclass_retyped.Below(z=2))
