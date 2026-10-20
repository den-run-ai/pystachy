# error: expected bool | float | int | None, got str
# lib/random's Random takes the seeds that its seed() takes (lib/README.md): no str
from random import Random

print(Random("pystachy").random())
