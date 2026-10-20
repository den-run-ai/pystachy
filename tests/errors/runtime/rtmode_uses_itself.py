# error: pys_m_gcd() implements an operation that it uses: write it without that operation
import math


def pys_m_gcd(a: int, b: int) -> int:
    return math.gcd(b, a % b) if b else a
