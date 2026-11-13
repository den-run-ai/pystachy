import hashlib
import sys


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    kind = sys.argv[2]
    rounds = int(sys.argv[3])
    d = ""
    for r in range(rounds):
        if kind == "sha1":
            d = hashlib.sha1(data).hexdigest()
        elif kind == "sha256":
            d = hashlib.sha256(data).hexdigest()
        else:
            d = hashlib.md5(data).hexdigest()
    print(kind, len(data), d)


main()
