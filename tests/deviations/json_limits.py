# Deliberate prototype boundaries: JSON integers are signed 64-bit values and
# decode/encode depth is at most 256 containers. CPython accepts these inputs.
import json


def main() -> None:
    for source in ["9223372036854775808", "-9223372036854775809"]:
        try:
            json.loads(source)
            print("integer accepted")
        except OverflowError as exc:
            print(str(exc))
    accepted = "[" * 256 + "0" + "]" * 256
    print(json.dumps(json.loads(accepted), separators=(",", ":")) == accepted)
    try:
        json.loads("[" * 257 + "0" + "]" * 257)
        print("depth accepted")
    except RecursionError as exc:
        print(str(exc))
    value = json.loads(accepted)
    if isinstance(value, list):
        # Appending an additional independently constructed child makes the same
        # root exceed the encoder's limit without converting container storage.
        deepest = json.loads("[0]")
        branch = value
        for _ in range(255):
            child = branch[0]
            if isinstance(child, list):
                branch = child
        branch[0] = deepest
        try:
            json.dumps(value)
            print("encode depth accepted")
        except RecursionError as exc:
            print(str(exc))


main()
