"""Decimal kernels: exact digits, remainders and sums, with the context restored."""
import decimal
import pytest

import decimal_factorial
import decimal_pi
import telco


@pytest.fixture
def context():
    # The kernels change the thread's context; later tests must not see it.
    saved = decimal.getcontext().copy()
    yield decimal.getcontext()
    decimal.setcontext(saved)


def test_decimal_pi(context):
    decimal_pi.bench_decimal_pi()
    assert context.prec == 19
    assert str(decimal_pi.pi_decimal()) == "3.141592653589793236"
    context.prec = 9
    assert str(decimal_pi.pi_decimal()) == "3.14159265"


def test_decimal_factorial(context):
    context.prec = decimal.MAX_PREC
    context.Emax = decimal.MAX_EMAX
    context.Emin = decimal.MIN_EMIN
    small = decimal_factorial.factorial(decimal.Decimal(20), 0) + decimal.Decimal(0)
    assert str(small) == "2432902008176640000"
    large = decimal_factorial.factorial(decimal.Decimal(1000), 0) + decimal.Decimal(0)
    assert large.adjusted() + 1 == 2568
    assert large % 1000000007 == 641419708
    assert large % 998244353 == 421678599


def test_telco(context):
    total, basic, distance = telco.bench_telco(2, telco.rel_path("data", "telco-bench.b"))
    assert context.rounding == decimal.ROUND_DOWN
    assert (str(total), str(basic), str(distance)) == ("5115.84", "293.90", "128.46")
    assert len(telco.TIMED) == 1
