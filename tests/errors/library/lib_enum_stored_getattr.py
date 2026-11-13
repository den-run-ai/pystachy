# error: 'Perm' object has no attribute ' enum int'
from enum import IntFlag


class Perm(IntFlag):
    READ = 1


print(getattr(Perm(0), " enum int"))
