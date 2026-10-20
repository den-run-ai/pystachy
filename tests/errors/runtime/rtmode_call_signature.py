# error: pys_m_gcd() is defined as double(double, double), but the compiler calls it as i64(i64, i64) (RUNTIME's m.gcd)
import math


def pys_m_gcd(a: float, b: float) -> float:
    return a


def pys_m_lcm(a: int, b: int) -> int:
    return math.gcd(a, b)
