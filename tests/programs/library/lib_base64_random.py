# Round trips, and a checksum of what every codec gives, over 400 pseudo-random inputs
import base64
import binascii

state = 12345


def rnd(n: int) -> int:
    global state
    state = (state * 1103515245 + 12345) & 0x7FFFFFFF
    return (state >> 8) % n


crc = 0
bad = 0
for case in range(400):
    n = rnd(70)
    kind = rnd(4)
    if kind == 0:
        d = bytes([rnd(256) for _ in range(n)])
    elif kind == 1:
        d = bytes([[0, 32, 255][rnd(3)] for _ in range(n)])
    elif kind == 2:
        d = bytes([rnd(4) * 85 for _ in range(n)])
    else:
        d = bytes([32 + rnd(95) for _ in range(n)])
    outs = [base64.b64encode(d), base64.urlsafe_b64encode(d), base64.b32encode(d), base64.b32hexencode(d),
            base64.b16encode(d), base64.a85encode(d), base64.a85encode(d, foldspaces=True, adobe=True, wrapcol=rnd(30)),
            base64.a85encode(d, pad=True), base64.b85encode(d), base64.b85encode(d, True), base64.z85encode(d),
            base64.encodebytes(d)]
    for o in outs:
        crc = binascii.crc32(o, crc)
    if base64.b64decode(outs[0]) != d or base64.urlsafe_b64decode(outs[1]) != d or base64.b32decode(outs[2]) != d:
        bad += 1
    if base64.b32hexdecode(outs[3]) != d or base64.b16decode(outs[4]) != d or base64.a85decode(outs[5]) != d:
        bad += 1
    if base64.a85decode(outs[6], foldspaces=True, adobe=True) != d or base64.b85decode(outs[8]) != d:
        bad += 1
    if base64.z85decode(outs[10]) != d or base64.decodebytes(outs[11]) != d or base64.a85decode(outs[7])[:n] != d:
        bad += 1
    # decoders on the raw bytes: results and errors
    for dec in range(6):
        try:
            if dec == 0:
                r = base64.b64decode(d)
            elif dec == 1:
                r = base64.b64decode(d, validate=True)
            elif dec == 2:
                r = base64.b32decode(d, casefold=True)
            elif dec == 3:
                r = base64.a85decode(d)
            elif dec == 4:
                r = base64.b85decode(d)
            else:
                r = base64.z85decode(d)
            crc = binascii.crc32(r, crc)
        except ValueError as e:
            crc = binascii.crc32(str(e).encode(), crc)
print(crc, bad)
