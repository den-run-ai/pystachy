import sys as system
from precision import Limits


class Precision:
    EPS = system.float_info.epsilon
    DIGITS = system.float_info.dig
    SCALED = 2 * system.float_info.epsilon


print(Precision.EPS, Precision.DIGITS, Precision.SCALED)
print(Limits.EPS, Limits.BITS, type(Limits.EPS).__name__, type(Limits.BITS).__name__)


class Info:
    epsilon = "custom"

class Environment:
    def __init__(self):
        self.float_info = Info()

class Reader:
    def __init__(self, system: Environment):
        self.eps = system.float_info.epsilon

print(Reader(Environment()).eps)
