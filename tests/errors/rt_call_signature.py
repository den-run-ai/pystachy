# error: pys_m_gcd() is called as i64(i64, i64) but defined as double(double, double)
import math


def pys_m_gcd(a: float, b: float) -> float:
    return a


def pys_m_lcm(a: int, b: int) -> int:
    return math.gcd(a, b)
