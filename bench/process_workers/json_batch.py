# pystachy: dynamic-any
"""An allocating native worker: repair a file of independent JSON lines."""
import json
import sys
from typing import Any

from json_repair import repair_json


def main() -> None:
    if len(sys.argv) != 3:
        raise ValueError("expected INPUT_FILE ROUNDS")
    rounds = int(sys.argv[2])
    if rounds < 1:
        raise ValueError("rounds must be positive")
    with open(sys.argv[1]) as stream:
        sources = stream.read().splitlines()
    outputs: list[Any] = []
    checksum = 0
    for iteration in range(rounds):
        for source in sources:
            value: Any = repair_json(source, return_objects=True)
            rendered = json.dumps(value, ensure_ascii=True, sort_keys=True)
            checksum += len(rendered)
            if iteration == 0:
                outputs.append(rendered)
    print(checksum)
    print(json.dumps(outputs, ensure_ascii=True))


if __name__ == "__main__":
    main()
