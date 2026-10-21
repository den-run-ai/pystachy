# sgp4's official verification, as its own test suite runs it (sgp4/tests.py of sgp4 2.27,
# test_satrec_against_tcppver_using_julian_dates), on 5 of the 33 satellites of SGP4-VER.TLE and a
# few of their times: Satrec.twoline2rv() and Satrec.sgp4(jd, fr) print the lines that Vallado's
# C++ SGP4 wrote to tcppver.out, and each is compared with the official line as the suite does
# (positions and velocities to 2e-7, the other fields as text).
from math import isnan, pi

from sgp4.api import SGP4_ERRORS, Satrec
from sgp4.earth_gravity import wgs72
from sgp4.ext import invjday, rv2coe

rad = 180.0 / pi
error = 2e-7

# SGP4-VER.TLE's lines (without the start, stop and step it appends to line 2) and, for some of the
# times it asks for, tcppver.out's line or the error that tests.py expects there: 00005 (SGP4),
# 08195 (SDP4, a Molniya orbit in 12-hour resonance), 28626 (SDP4, geosynchronous), 28872 (SGP4 with
# the simplified drag of a low perigee, decaying: error 6) and 33334 (error 3 at its epoch).
CASES = [
    ('1 00005U 58002B   00179.78495062  .00000023  00000-0  28098-4 0  4753',
     '2 00005  34.2682 348.7242 1859667 331.7664  19.3264 10.82419157413667',
     [(0.0, '       0.00000000    7022.46529266   -1400.08296755       0.03995155  1.893841015  6.405893759  4.534807250'),
      (360.0, '     360.00000000   -7154.03120202   -3783.17682504   -3536.19412294  4.741887409 -4.151817765 -2.093935425    8635.341424 0.185684   34.26805  347.97998  332.85746  252.46796  273.52819  2000  6 28  0:50:19.733571'),
      (1440.0, '    1440.00000000    -938.55923943   -6268.18748831   -4294.02924751  7.536105209 -0.427127707  0.989878080    8632.098491 0.185801   34.25571  345.65357  336.33937  298.48507  315.94715  2000  6 28 18:50:19.733571'),
      (2880.0, '    2880.00000000   -8650.73082219   -1914.93811525   -3007.03603443  3.067165127 -4.828384068 -2.515322836    8636.101255 0.185538   34.27261  342.61158  340.69038  234.10932  252.77706  2000  6 29 18:50:19.733571'),
      (4320.0, '    4320.00000000   -9060.47373569    4658.70952502     813.68673153 -2.232832783 -4.110453490 -3.157345433    8637.006122 0.185080   34.28036  339.51733  345.34018  186.53394  189.32850  2000  6 30 18:50:19.733571')]),
    ('1 08195U 75081A   06176.33215444  .00000099  00000-0  11873-3 0   813',
     '2 08195  64.1586 279.0717 6877146 264.7651  20.2257  2.00491383225656',
     [(0.0, '       0.00000000    2349.89483350  -14785.93811562       0.02119378  2.721488096 -3.256811655  4.498416672'),
      (120.0, '     120.00000000   15223.91713658  -17852.95881713   25280.39558224  1.079041732  0.875187372  2.485682813   26564.959894 0.686668   64.17478  279.02552  264.80305  149.71445   80.31676  2006  6 25  9:58:18.143649'),
      (1440.0, '    1440.00000000    2890.80638268  -15446.43952300     948.77010176  2.654407490 -2.909344895  4.486437362   26574.377821 0.686612   64.17922  278.92626  264.80655   99.03224   21.92752  2006  6 26  7:58:18.143636'),
      (2880.0, '    2880.00000000    3417.20931586  -16038.79510665    1894.74934058  2.585515864 -2.596818146  4.456882556   26573.377678 0.686536   64.17812  278.82248  264.79245  102.53328   23.70751  2006  6 27  7:58:18.143636')]),
    ('1 28626U 05008A   06176.46683397 -.00000205  00000-0  10000-3 0  2190',
     '2 28626   0.0019 286.9433 0000335  13.7918  55.6504  1.00270176  4891',
     [(0.0, '       0.00000000   42080.71852213   -2646.86387436       0.81851294  0.193105177  3.068688251  0.000438449'),
      (720.0, '     720.00000000  -42103.20138132    2291.06228893      -0.13274964 -0.166974816 -3.070104560 -0.000311007   42166.272504 0.000034    0.00580  355.10258  238.21722  303.56550  303.56870  2006  6 25 23:12:14.455012'),
      (1440.0, '    1440.00000000   42119.96263499   -1925.77567263      -0.19827433  0.140521206  3.071541613  0.000179561   42166.304886 0.000062    0.00336    1.98591  328.51675   26.87953   26.87630  2006  6 26 11:12:14.455012')]),
    ('1 28872U 05037B   05333.02012661  .25992681  00000-0  24476-3 0  1534',
     '2 28872  96.4736 157.9986 0303955 244.0492 110.6523 16.46015938 10708',
     [(0.0, '       0.00000000   -6131.82730456    2446.52815528    -253.64211033 -0.144920228  0.995100963  7.658645067'),
      (5.0, '       5.00000000   -5799.24256134    2589.14811119    2011.54515100  2.325207364 -0.047125672  7.296234071    6532.131812 0.028892   96.46953  157.99929  243.05004  134.64086  132.24900  2005 11 29  0:33:58.939092'),
      (25.0, '      25.00000000     896.73799533     447.12357305    6607.22400507  6.983396282 -2.925846168 -0.872655207    6512.862228 0.030569   96.47849  158.01759  245.19289  210.51094  212.32507  2005 11 29  0:53:58.939101'),
      (50.0, '      50.00000000    5548.43325922   -2480.16469245   -1979.24314527 -2.763269534  0.199691915 -7.482796996    6528.353658 0.028906   96.46957  158.03163  242.90998  315.24831  317.54473  2005 11 29  1:18:58.939092'),
      (55.0, 'error 6')]),
    ('1 33334U 78066F   06174.85818871  .00000620  00000-0  10000-3 0  6809',
     '2 33334  68.4714 236.1303 5602877 123.7484 302.5767  0.00001000 67521',
     [(0.0, 'error 3')]),
]


def format_short_line(tsince, r, v):
    """Short line, using the same format string that testcpp.cpp uses."""

    return ' %16.8f %16.8f %16.8f %16.8f %12.9f %12.9f %12.9f\n' % (
        tsince, r[0], r[1], r[2], v[0], v[1], v[2])


def format_long_line(satrec, tsince, mu, r, v):
    """Long line, using the same format string that testcpp.cpp uses."""

    short = format_short_line(tsince, r, v).strip('\n')

    jd = satrec.jdsatepoch + satrec.jdsatepochF + tsince / 1440.0
    year, mon, day, hr, minute, sec = invjday(jd)

    (p, a, ecc, incl, node, argp, nu, m, arglat, truelon, lonper
     ) = rv2coe(r, v, mu)

    return short + (
        ' %14.6f %8.6f %10.5f %10.5f %10.5f %10.5f %10.5f'
        ' %5i%3i%3i %2i:%2i:%9.6f\n'
    ) % (
        a, ecc, incl*rad, node*rad, argp*rad, nu*rad,
        m*rad, year, mon, day, hr, minute, sec,
    )


def invoke(satrec, tsince):
    whole, fraction = divmod(tsince / 1440.0, 1.0)
    jd = satrec.jdsatepoch + whole
    fr = satrec.jdsatepochF + fraction
    e, r, v = satrec.sgp4(jd, fr)
    assert e == satrec.error
    return e, r, v


def similar(actual_line, expected_line):
    # tests.py's comparison: the first seven fields are printed to very high precision, so a
    # small error due to rounding differences is allowed; the rest are compared as text
    afields = actual_line.split()
    efields = expected_line.split()
    actual7 = [float(a) for a in afields[:7]]
    expected7 = [float(e) for e in efields[:7]]
    return (len(actual7) == len(expected7)
            and all(-error < (a - e) < error for a, e in zip(actual7, expected7))
            and afields[7:] == efields[7:])


mu = wgs72.mu
lines = 0
mismatches = 0
error_list: list[int] = []
for line1, line2, times in CASES:
    satrec = Satrec.twoline2rv(line1, line2)
    print('%d xx' % satrec.satnum)
    for tsince, expected in times:
        e, r, v = invoke(satrec, tsince)
        if e != 0:
            error_list.append(e)
            actual = 'error %d' % e
            print(actual, '(%s): %s; nan: %s' % (SGP4_ERRORS[e], satrec.error_message, isnan(r[0])))
            ok = actual == expected
        else:
            if tsince == 0.0:
                actual = format_short_line(tsince, r, v)
            else:
                actual = format_long_line(satrec, tsince, mu, r, v)
            print(actual, end='')
            ok = not expected.startswith('error') and similar(actual, expected)
        lines += 1
        if not ok:
            mismatches += 1
            print('MISMATCH: expected', repr(expected))
print('lines', lines, 'mismatches', mismatches, 'errors', error_list)
