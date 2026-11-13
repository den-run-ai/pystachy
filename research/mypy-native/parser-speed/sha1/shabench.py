import sys
from sha1mod import sha1_hex


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    rounds = int(sys.argv[2])
    d = ""
    for r in range(rounds):
        d = sha1_hex(data)
    print(len(data), d)


main()
