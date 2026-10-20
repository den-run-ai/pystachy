# sgp4's API (sgp4 2.27's Satrec, jday and days2mdhms, and the helpers they use), on the cases of
# an evaluation of the port and of an independent check of it: a TLE's fields, propagation by
# Julian date and by minutes since the epoch, the three gravity models, Satrec.sgp4init() in both
# operation modes, Alpha-5 satellite numbers, malformed and non-ASCII TLEs, times far from the
# epoch, epoch fields that datetime() rejects, and rv2coe() on degenerate orbits. It ends with an
# error that nothing catches.
from sgp4.alpha5 import from_alpha5, to_alpha5
from sgp4.api import SGP4_ERRORS, WGS72, WGS72OLD, WGS84, Satrec, accelerated, days2mdhms, jday
from sgp4.earth_gravity import wgs72, wgs84
from sgp4.ext import invjday, rv2coe

print("accelerated:", accelerated)

# the ISS (near-earth: SGP4)
s = '1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991'
t = '2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482'
sat = Satrec.twoline2rv(s, t)
print(sat.satnum_str, sat.classification, sat.intldesg, sat.epochyr, repr(sat.epochdays),
      repr(sat.jdsatepoch), repr(sat.jdsatepochF))
print(sat.method, sat.isimp, sat.operationmode, repr(sat.no_kozai), repr(sat.bstar), repr(sat.ecco),
      repr(sat.inclo), sat.revnum, sat.ephtype, sat.elnum, sat.error, sat.error_message)
jd, fr = jday(2019, 12, 9, 12, 0, 0)
print(repr(jd), repr(fr))
print(sat.sgp4(jd, fr))
for minutes in [0.0, 1.0, 90.0, 1440.0, -1440.0, 10080.0]:
    e, r, v = sat.sgp4_tsince(minutes)
    print("%10.2f %d %16.8f %16.8f %16.8f %12.9f %12.9f %12.9f" % (minutes, e, r[0], r[1], r[2], v[0], v[1], v[2]))
for g in [WGS72OLD, WGS84]:
    print(g, Satrec.twoline2rv(s, t, g).sgp4_tsince(1440.0))
print(wgs84, wgs72.j3oj2 == wgs72.j3 / wgs72.j2)

# times far from the epoch: an orbit that no longer exists (error 1), NaN
for m in [1e6, -1e6, 1e15, float("nan")]:
    e, r, v = sat.sgp4_tsince(m)
    print(m, e, sat.error_message, r, v)
print(sat.sgp4(2.0 ** 62, 0.0))

# a satellite that decays: error 6 after a day
dec = Satrec.twoline2rv('1 29238U 06022G   06177.28732010  .00766286  10823-4  13334-2 0   101',
                        '2 29238  51.5595 213.7903 0202579  95.2503 267.9010 15.73823839  1061')
for minutes in [0.0, 1440.0, 2880.0]:
    e, r, v = dec.sgp4_tsince(minutes)
    print(minutes, e, SGP4_ERRORS.get(e, "ok"))

# sgp4init() itself, in the improved and the AFSPC modes, with Alpha-5 satellite numbers
for n, mode in [(5, 'i'), (5, 'a'), (339999, 'i'), (340000, 'i')]:
    x = Satrec()
    try:
        x.sgp4init(WGS72, mode, n, 18441.785, 2.8098e-05, 6.969196665e-13, 0.0, 0.1859667,
                   5.7904160274885, 0.5980929187319, 0.3373093125574, 0.0472294454407,
                   6.0863854713832)
        print(x.satnum_str, x.epochyr, repr(x.epochdays), x.revnum, x.sgp4_tsince(360.0))
    except ValueError as ex:
        print(n, "ValueError:", ex)
a5 = Satrec.twoline2rv(s.replace('25544', 'T0001'), t.replace('25544', 'T0001'))
print(a5.satnum_str, from_alpha5(a5.satnum_str), from_alpha5('Z9999'), from_alpha5('J0000'),
      from_alpha5('P1234'), from_alpha5('00042'))
# the properties no and satnum, the slots, and whole Julian days as ints
print(repr(sat.no), sat.no == sat.no_kozai, sat.satnum, a5.satnum, dec.satnum)
print(len(Satrec.__slots__), sat.__slots__[0], sat.__slots__[-1], sat.sgp4(2458827, 0) == sat.sgp4(2458827.0, 0.0))
for n in [99999, 100000, 182345, 339999, 340000, 9223372036854775807]:
    try:
        print(n, to_alpha5(n))
    except ValueError as ex:
        print(n, "ValueError:", ex)

# malformed TLEs: the complete messages (with braces in the line, which str.format left alone),
# lines that do not match, non-ASCII characters, and a revnum or ephtype that is not a number
for l1, l2 in [(s[:60] + '{0}{1}', t), (s, t[:50] + '{2}'), (s[:40], t), ('', ''),
             (s, t.replace('2 25544', '2 25545')), (s.replace('98067A', '98067\u00e9'), t),
             (s, t.replace(' 15.501', '\u00a015.501')), (s, t[:63] + 'ABCDE' + t[68:]),
             (s[:62] + 'X' + s[63:], t), (s[:62] + ' ' + s[63:], t[:63] + '    7' + t[68:])]:
    try:
        x = Satrec.twoline2rv(l1, l2)
        print("parsed", x.revnum, x.ephtype)
    except ValueError as ex:
        print("ValueError:", ex)

# epoch fields that float() reads but no TLE writes (negative, an exponent, an infinity): the
# checks datetime() makes of the legacy epoch's date reject the dates it cannot hold
for f in ['-99.99999999', '999.99e+5   ', '-99.9e+4    ', '999.9999e+9 ', '-99.999e+9  ',
          '999.9999e999']:
    try:
        x = Satrec.twoline2rv(s[:20] + f + s[32:], t)
        print(repr(f), x.epochyr, repr(x.epochdays), repr(x.jdsatepoch), repr(x.jdsatepochF))
    except (ValueError, OverflowError) as ex:
        print(repr(f), type(ex).__name__ + ":", ex)

# dates
print(jday(-4712, 1, 1, 12, 0, 0), jday(9999, 12, 31, 23, 59, 59.999999))
print(days2mdhms(2000, 1.0), days2mdhms(2000, 32.0), days2mdhms(2000, 366.0))
print(days2mdhms(2024, 366.99999999999), days2mdhms(2023, 0.0), days2mdhms(2023, 1e-12, 0))
print(invjday(0.0), invjday(1e9), invjday(2460000.123456789))

# rv2coe() on degenerate and special orbits: no angular momentum, radial, circular equatorial,
# circular inclined, elliptical equatorial, hyperbolic
mu = wgs72.mu
for r, v in [((7000.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((7000.0, 0.0, 0.0), (7.0, 0.0, 0.0)),
             ((7000.0, 0.0, 0.0), (0.0, 7.546049108166282, 0.0)),
             ((7000.0, 0.0, 0.0), (0.0, 5.0, 5.0)), ((7000.0, 100.0, 0.0), (0.0, 9.0, 0.0)),
             ((-1e7, 1e-9, 3.0), (1e-3, -2.0, 0.5))]:
    p, a, ecc, incl, omega, argp, nu, m, arglat, truelon, lonper = rv2coe(r, v, mu)
    print(p, a, ecc, incl, omega, argp, nu, m, arglat, truelon, lonper)

Satrec.twoline2rv(s, t.replace('2 25544', '2 25545'))
print("not reached")
