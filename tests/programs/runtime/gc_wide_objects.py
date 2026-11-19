# Objects of 136 bytes and more (17, 20, 40 and 130 fields): every field as its constructor
# set it, in chains that survive collections while most objects die, and after their memory
# is reused. The allocator takes such sizes from other free lists than the small ones.


class W17:
    def __init__(self, seed: int, link: "W17 | None") -> None:
        self.f0 = seed + 0
        self.f1 = seed + 1
        self.f2 = seed + 2
        self.f3 = "s" + str(seed + 3)
        self.f4 = [seed, 4]
        self.f5 = seed + 5
        self.f6 = seed + 6
        self.f7 = seed + 7
        self.f8 = "s" + str(seed + 8)
        self.f9 = [seed, 9]
        self.f10 = seed + 10
        self.f11 = seed + 11
        self.f12 = seed + 12
        self.f13 = "s" + str(seed + 13)
        self.f14 = [seed, 14]
        self.f15 = seed + 15
        self.f16: "W17 | None" = link

    def total(self) -> int:
        return self.f0 + self.f1 + self.f2 + len(self.f3) + self.f4[0] + self.f4[1] + self.f5 + self.f6 + self.f7 \
            + len(self.f8) + self.f9[0] + self.f9[1] + self.f10 + self.f11 + self.f12 + len(self.f13) + self.f14[0] + self.f14[1] + self.f15


class W20:
    def __init__(self, seed: int, link: "W20 | None") -> None:
        self.f0 = seed + 0
        self.f1 = seed + 1
        self.f2 = seed + 2
        self.f3 = "s" + str(seed + 3)
        self.f4 = [seed, 4]
        self.f5 = seed + 5
        self.f6 = seed + 6
        self.f7 = seed + 7
        self.f8 = "s" + str(seed + 8)
        self.f9 = [seed, 9]
        self.f10 = seed + 10
        self.f11 = seed + 11
        self.f12 = seed + 12
        self.f13 = "s" + str(seed + 13)
        self.f14 = [seed, 14]
        self.f15 = seed + 15
        self.f16 = seed + 16
        self.f17 = seed + 17
        self.f18 = "s" + str(seed + 18)
        self.f19: "W20 | None" = link

    def total(self) -> int:
        return self.f0 + self.f1 + self.f2 + len(self.f3) + self.f4[0] + self.f4[1] + self.f5 + self.f6 + self.f7 \
            + len(self.f8) + self.f9[0] + self.f9[1] + self.f10 + self.f11 + self.f12 + len(self.f13) + self.f14[0] + self.f14[1] + self.f15 \
            + self.f16 + self.f17 + len(self.f18)


class W40:
    def __init__(self, seed: int, link: "W40 | None") -> None:
        self.f0 = seed + 0
        self.f1 = seed + 1
        self.f2 = seed + 2
        self.f3 = "s" + str(seed + 3)
        self.f4 = [seed, 4]
        self.f5 = seed + 5
        self.f6 = seed + 6
        self.f7 = seed + 7
        self.f8 = "s" + str(seed + 8)
        self.f9 = [seed, 9]
        self.f10 = seed + 10
        self.f11 = seed + 11
        self.f12 = seed + 12
        self.f13 = "s" + str(seed + 13)
        self.f14 = [seed, 14]
        self.f15 = seed + 15
        self.f16 = seed + 16
        self.f17 = seed + 17
        self.f18 = "s" + str(seed + 18)
        self.f19 = [seed, 19]
        self.f20 = seed + 20
        self.f21 = seed + 21
        self.f22 = seed + 22
        self.f23 = "s" + str(seed + 23)
        self.f24 = [seed, 24]
        self.f25 = seed + 25
        self.f26 = seed + 26
        self.f27 = seed + 27
        self.f28 = "s" + str(seed + 28)
        self.f29 = [seed, 29]
        self.f30 = seed + 30
        self.f31 = seed + 31
        self.f32 = seed + 32
        self.f33 = "s" + str(seed + 33)
        self.f34 = [seed, 34]
        self.f35 = seed + 35
        self.f36 = seed + 36
        self.f37 = seed + 37
        self.f38 = "s" + str(seed + 38)
        self.f39: "W40 | None" = link

    def total(self) -> int:
        return self.f0 + self.f1 + self.f2 + len(self.f3) + self.f4[0] + self.f4[1] + self.f5 + self.f6 + self.f7 \
            + len(self.f8) + self.f9[0] + self.f9[1] + self.f10 + self.f11 + self.f12 + len(self.f13) + self.f14[0] + self.f14[1] + self.f15 \
            + self.f16 + self.f17 + len(self.f18) + self.f19[0] + self.f19[1] + self.f20 + self.f21 + self.f22 + len(self.f23) \
            + self.f24[0] + self.f24[1] + self.f25 + self.f26 + self.f27 + len(self.f28) + self.f29[0] + self.f29[1] + self.f30 + self.f31 \
            + self.f32 + len(self.f33) + self.f34[0] + self.f34[1] + self.f35 + self.f36 + self.f37 + len(self.f38)


class W130:
    def __init__(self, seed: int, link: "W130 | None") -> None:
        self.f0 = seed + 0
        self.f1 = seed + 1
        self.f2 = seed + 2
        self.f3 = "s" + str(seed + 3)
        self.f4 = [seed, 4]
        self.f5 = seed + 5
        self.f6 = seed + 6
        self.f7 = seed + 7
        self.f8 = "s" + str(seed + 8)
        self.f9 = [seed, 9]
        self.f10 = seed + 10
        self.f11 = seed + 11
        self.f12 = seed + 12
        self.f13 = "s" + str(seed + 13)
        self.f14 = [seed, 14]
        self.f15 = seed + 15
        self.f16 = seed + 16
        self.f17 = seed + 17
        self.f18 = "s" + str(seed + 18)
        self.f19 = [seed, 19]
        self.f20 = seed + 20
        self.f21 = seed + 21
        self.f22 = seed + 22
        self.f23 = "s" + str(seed + 23)
        self.f24 = [seed, 24]
        self.f25 = seed + 25
        self.f26 = seed + 26
        self.f27 = seed + 27
        self.f28 = "s" + str(seed + 28)
        self.f29 = [seed, 29]
        self.f30 = seed + 30
        self.f31 = seed + 31
        self.f32 = seed + 32
        self.f33 = "s" + str(seed + 33)
        self.f34 = [seed, 34]
        self.f35 = seed + 35
        self.f36 = seed + 36
        self.f37 = seed + 37
        self.f38 = "s" + str(seed + 38)
        self.f39 = [seed, 39]
        self.f40 = seed + 40
        self.f41 = seed + 41
        self.f42 = seed + 42
        self.f43 = "s" + str(seed + 43)
        self.f44 = [seed, 44]
        self.f45 = seed + 45
        self.f46 = seed + 46
        self.f47 = seed + 47
        self.f48 = "s" + str(seed + 48)
        self.f49 = [seed, 49]
        self.f50 = seed + 50
        self.f51 = seed + 51
        self.f52 = seed + 52
        self.f53 = "s" + str(seed + 53)
        self.f54 = [seed, 54]
        self.f55 = seed + 55
        self.f56 = seed + 56
        self.f57 = seed + 57
        self.f58 = "s" + str(seed + 58)
        self.f59 = [seed, 59]
        self.f60 = seed + 60
        self.f61 = seed + 61
        self.f62 = seed + 62
        self.f63 = "s" + str(seed + 63)
        self.f64 = [seed, 64]
        self.f65 = seed + 65
        self.f66 = seed + 66
        self.f67 = seed + 67
        self.f68 = "s" + str(seed + 68)
        self.f69 = [seed, 69]
        self.f70 = seed + 70
        self.f71 = seed + 71
        self.f72 = seed + 72
        self.f73 = "s" + str(seed + 73)
        self.f74 = [seed, 74]
        self.f75 = seed + 75
        self.f76 = seed + 76
        self.f77 = seed + 77
        self.f78 = "s" + str(seed + 78)
        self.f79 = [seed, 79]
        self.f80 = seed + 80
        self.f81 = seed + 81
        self.f82 = seed + 82
        self.f83 = "s" + str(seed + 83)
        self.f84 = [seed, 84]
        self.f85 = seed + 85
        self.f86 = seed + 86
        self.f87 = seed + 87
        self.f88 = "s" + str(seed + 88)
        self.f89 = [seed, 89]
        self.f90 = seed + 90
        self.f91 = seed + 91
        self.f92 = seed + 92
        self.f93 = "s" + str(seed + 93)
        self.f94 = [seed, 94]
        self.f95 = seed + 95
        self.f96 = seed + 96
        self.f97 = seed + 97
        self.f98 = "s" + str(seed + 98)
        self.f99 = [seed, 99]
        self.f100 = seed + 100
        self.f101 = seed + 101
        self.f102 = seed + 102
        self.f103 = "s" + str(seed + 103)
        self.f104 = [seed, 104]
        self.f105 = seed + 105
        self.f106 = seed + 106
        self.f107 = seed + 107
        self.f108 = "s" + str(seed + 108)
        self.f109 = [seed, 109]
        self.f110 = seed + 110
        self.f111 = seed + 111
        self.f112 = seed + 112
        self.f113 = "s" + str(seed + 113)
        self.f114 = [seed, 114]
        self.f115 = seed + 115
        self.f116 = seed + 116
        self.f117 = seed + 117
        self.f118 = "s" + str(seed + 118)
        self.f119 = [seed, 119]
        self.f120 = seed + 120
        self.f121 = seed + 121
        self.f122 = seed + 122
        self.f123 = "s" + str(seed + 123)
        self.f124 = [seed, 124]
        self.f125 = seed + 125
        self.f126 = seed + 126
        self.f127 = seed + 127
        self.f128 = "s" + str(seed + 128)
        self.f129: "W130 | None" = link

    def total(self) -> int:
        return self.f0 + self.f1 + self.f2 + len(self.f3) + self.f4[0] + self.f4[1] + self.f5 + self.f6 + self.f7 \
            + len(self.f8) + self.f9[0] + self.f9[1] + self.f10 + self.f11 + self.f12 + len(self.f13) + self.f14[0] + self.f14[1] + self.f15 \
            + self.f16 + self.f17 + len(self.f18) + self.f19[0] + self.f19[1] + self.f20 + self.f21 + self.f22 + len(self.f23) \
            + self.f24[0] + self.f24[1] + self.f25 + self.f26 + self.f27 + len(self.f28) + self.f29[0] + self.f29[1] + self.f30 + self.f31 \
            + self.f32 + len(self.f33) + self.f34[0] + self.f34[1] + self.f35 + self.f36 + self.f37 + len(self.f38) + self.f39[0] + self.f39[1] \
            + self.f40 + self.f41 + self.f42 + len(self.f43) + self.f44[0] + self.f44[1] + self.f45 + self.f46 + self.f47 \
            + len(self.f48) + self.f49[0] + self.f49[1] + self.f50 + self.f51 + self.f52 + len(self.f53) + self.f54[0] + self.f54[1] + self.f55 \
            + self.f56 + self.f57 + len(self.f58) + self.f59[0] + self.f59[1] + self.f60 + self.f61 + self.f62 + len(self.f63) \
            + self.f64[0] + self.f64[1] + self.f65 + self.f66 + self.f67 + len(self.f68) + self.f69[0] + self.f69[1] + self.f70 + self.f71 \
            + self.f72 + len(self.f73) + self.f74[0] + self.f74[1] + self.f75 + self.f76 + self.f77 + len(self.f78) + self.f79[0] + self.f79[1] \
            + self.f80 + self.f81 + self.f82 + len(self.f83) + self.f84[0] + self.f84[1] + self.f85 + self.f86 + self.f87 \
            + len(self.f88) + self.f89[0] + self.f89[1] + self.f90 + self.f91 + self.f92 + len(self.f93) + self.f94[0] + self.f94[1] + self.f95 \
            + self.f96 + self.f97 + len(self.f98) + self.f99[0] + self.f99[1] + self.f100 + self.f101 + self.f102 + len(self.f103) \
            + self.f104[0] + self.f104[1] + self.f105 + self.f106 + self.f107 + len(self.f108) + self.f109[0] + self.f109[1] + self.f110 + self.f111 \
            + self.f112 + len(self.f113) + self.f114[0] + self.f114[1] + self.f115 + self.f116 + self.f117 + len(self.f118) + self.f119[0] + self.f119[1] \
            + self.f120 + self.f121 + self.f122 + len(self.f123) + self.f124[0] + self.f124[1] + self.f125 + self.f126 + self.f127 \
            + len(self.f128)


def churn17(rounds: int) -> int:
    keep: W17 | None = None
    acc = 0
    for r in range(rounds):
        o = W17(r, keep if r % 7 == 0 else None)
        acc += o.total()
        if r % 7 == 0:
            keep = o
    n = 0
    while keep is not None:
        acc += keep.total()
        keep = keep.f16
        n += 1
    return acc * 1000 + n


def churn20(rounds: int) -> int:
    keep: W20 | None = None
    acc = 0
    for r in range(rounds):
        o = W20(r, keep if r % 5 == 0 else None)
        acc += o.total()
        if r % 5 == 0:
            keep = o
    n = 0
    while keep is not None:
        acc += keep.total()
        keep = keep.f19
        n += 1
    return acc * 1000 + n


def churn40(rounds: int) -> int:
    keep: W40 | None = None
    acc = 0
    for r in range(rounds):
        o = W40(r, keep if r % 3 == 0 else None)
        acc += o.total()
        if r % 3 == 0:
            keep = o
    n = 0
    while keep is not None:
        acc += keep.total()
        keep = keep.f39
        n += 1
    return acc * 1000 + n


def churn130(rounds: int) -> int:
    keep: W130 | None = None
    acc = 0
    for r in range(rounds):
        o = W130(r, keep if r % 4 == 0 else None)
        acc += o.total()
        if r % 4 == 0:
            keep = o
    n = 0
    while keep is not None:
        acc += keep.total()
        keep = keep.f129
        n += 1
    return acc * 1000 + n


print(churn17(4000), churn20(4000), churn40(3000), churn130(1500))
a = W17(1, None)
b = W17(2, a)
print(a.f0, a.f3, a.f4, a.f16 is None, b.f16 is a, b.total())
c = W130(5, None)
print(c.f0, c.f128, c.f129 is None, c.f124, c.total())
