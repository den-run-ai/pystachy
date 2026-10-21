# jdcal's conversions between calendar dates and Julian dates: the cases of its own test suite
# (test_jdcal.py of jdcal 1.4.1, run under pytest there) and the examples of its docstrings, as
# a program
import jdcal
from jdcal import MJD_0
from jdcal import MJD_JD2000
from jdcal import gcal2jd
from jdcal import ipart
from jdcal import is_leap
from jdcal import jcal2jd
from jdcal import jd2gcal
from jdcal import jd2jcal

print(jdcal.__version__, MJD_0, MJD_JD2000, MJD_0 + MJD_JD2000 + 0.5)

# test_ipart (and -0.0, which round() keeps)
print(ipart(20.345), ipart(-20.345), ipart(0.12345), ipart(-0.6789), round(ipart(-0.6789), 12))

# test_is_leap. Upstream's is_leap gives a float for a year divisible by 4 but not by 100
# (4.0 for 2004), and the port gives True (PORT.md): the program prints the truth value
for y in [2000, 2001, 2004, 1000, 1998, 1992, 1900, 1600, 0, -4, -100]:
    print(y, "leap" if is_leap(y) else "common", not is_leap(y))

# test_gcal2jd_simple, and the docstrings' dates (with 1582 and 9999) in both calendars and back
print(gcal2jd(2000, 1, 1), jcal2jd(2000, 1, 1))
YEARS = [-4699, -2114, -1050, -123, -1, 0, 1, 123, 1582, 1678, 2000, 2012, 2245, 9999]
MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 9, 10, 11, 12, 12]
DAYS = [1, 12, 23, 14, 25, 16, 27, 8, 15, 9, 10, 11, 31, 31]
for i in range(len(YEARS)):
    g = gcal2jd(YEARS[i], MONTHS[i], DAYS[i])
    j = jcal2jd(YEARS[i], MONTHS[i], DAYS[i])
    print(YEARS[i], MONTHS[i], DAYS[i], g[1], j[1], jd2gcal(g[0], g[1]), jd2jcal(j[0], j[1]),
          jd2jcal(g[0], g[1]), jd2gcal(j[0], j[1]))

# test_gcal2jd_negative_numbers_and_zero, test_gcal2jd_next_month and the docstring's month 0:
# out-of-range months and days carry over
SAME = [
    ((2000, -2, -4), (1999, 9, 26)), ((2000, 2, -1), (2000, 1, 30)),
    ((2000, 3, -1), (2000, 2, 28)), ((2000, 3, 0), (2000, 2, 29)), ((2001, 3, 0), (2001, 2, 28)),
    ((2000, 2, 30), (2000, 3, 1)), ((2001, 2, 30), (2001, 3, 2)), ((2000, 12, 32), (2001, 1, 1)),
    ((2000, 0, 1), (1999, 12, 1)), ((2000, 13, 1), (2001, 1, 1)), ((2000, -1, -1), (1999, 10, 30)),
]
for a, b in SAME:
    ga = gcal2jd(a[0], a[1], a[2])
    print(a, b, ga, ga == gcal2jd(b[0], b[1], b[2]), jd2gcal(ga[0], ga[1]))

# test_gcal2jd_is_for_mid_night_of_given_day passes days 3.5 and 25.9, which gcal2jd truncates
# with int(); the port takes int arguments (PORT.md), so the program truncates them
print(gcal2jd(1996, 4, 3) == gcal2jd(1996, 4, int(3.5)), gcal2jd(2000, 10, int(25.9)))

# test_jd2gcal: round trips (jd2gcal(*gcal2jd(...)) upstream; star arguments, PORT.md)
for y, m, d in [(2000, 1, 1), (1950, 1, 1), (1999, 10, 12), (2000, 2, 30), (2000, -2, -4),
                (-1999, 10, 12), (-4000, 10, 11)]:
    g = gcal2jd(y, m, d)
    j = jcal2jd(y, m, d)
    print((y, m, d), jd2gcal(g[0], g[1]), jd2jcal(j[0], j[1]))

# test_jd2gcal_fractional_day_part and the docstrings' fractions of a day
for mjd in [51544.0, 51544.5, 51544.245, 51544.1, 51544.75, 51544.0 + 0.245, 51544.999]:
    r = jd2gcal(MJD_0, mjd)
    s = jd2jcal(MJD_0, mjd + 13.0)
    print(mjd, r, s, round(r[-1], 10), round(r[-1], 10) == round(mjd - 51544.0, 10))
# the two parts split anywhere, and either can be negative
print(jd2gcal(2451545.0, 0.0), jd2gcal(2451545.0, -0.5), jd2gcal(2451544.5, 0.5))
print(jd2gcal(2400000.5, -51544.75), jd2gcal(0.0, 0.0), jd2jcal(0.0, 0.0), jd2jcal(-0.25, 0.25))
print(jd2gcal(2451545.4, 0.3), jd2gcal(2451545.6, -0.3), jd2jcal(2451545.75, -1.5))

# Excel's serial dates, as openpyxl's to_excel and from_excel converted them with jdcal (up to
# openpyxl 3.0.6): days since 1899-12-30, with Excel's 29 February 1900 below day 61. Serials 1
# to 59 are a day later than that count (serial 1 is 1 January 1900), as to_excel makes them:
# openpyxl 3.0.6's from_excel left serial 1 out (1 < value), which 3.1 corrects (0 < value)
WINDOWS_1900 = sum(gcal2jd(1899, 12, 30))
MAC_1904 = sum(gcal2jd(1904, 1, 1))
print(WINDOWS_1900, MAC_1904)
for y, m, d in [(1900, 1, 1), (1900, 2, 28), (1900, 3, 1), (2024, 2, 29), (9999, 12, 31)]:
    jul = sum(gcal2jd(y, m, d)) - WINDOWS_1900
    if jul <= 60:
        jul -= 1
    print((y, m, d), jul, sum(gcal2jd(y, m, d)) - MAC_1904)
for value in [1.0, 59.0, 60.0, 61.0, 45351.75, 2958465.5]:
    if 0 < value < 60:
        value += 1
    print(value, jd2gcal(MJD_0, value + WINDOWS_1900 - MJD_0))

# test_jcal2jd_and_back_through_jd2jcal, with a linear congruential generator in place of
# random: 1000 dates from 4700 BC to AD 2200, both calendars, and across them
state = 2026


def draw(lo: int, hi: int) -> int:
    global state
    state = (state * 1103515245 + 12345) % 2147483648
    return lo + (state >> 8) % (hi - lo + 1)


bad = 0
fmax = 0.0
total = 0.0
for i in range(1000):
    y = draw(-4699, 2200)
    m = draw(1, 12)
    d = draw(1, 28)
    j = jcal2jd(y, m, d)
    x = jd2jcal(MJD_0, j[1])
    g = gcal2jd(y, m, d)
    r = jd2gcal(g[0], g[1])
    c = jd2gcal(j[0], j[1])
    k = jd2jcal(g[0], g[1])
    if x[0] != y or x[1] != m or x[2] != d or r[0] != y or r[1] != m or r[2] != d:
        bad += 1
    if gcal2jd(c[0], c[1], c[2]) != j or jcal2jd(k[0], k[1], k[2]) != g:
        bad += 1
    fmax = max(fmax, x[3], r[3])
    total += g[1] - j[1]
print(bad, fmax, total, state)
