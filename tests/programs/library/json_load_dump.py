# json.load(fp) and json.dump(obj, fp) with typed JSON values.
import json
import os
import tempfile


def main() -> None:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "a.json")
    with open(p, "w") as f:
        json.dump({"a": [1, 2.5, None, True, "x"]}, f)
    with open(p) as f:
        print(f.read())
    with open(p) as f:
        back = json.load(f)
    print(back, json.dumps(back, sort_keys=True))


main()
