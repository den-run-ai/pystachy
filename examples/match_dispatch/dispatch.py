"""A typed command processor using tuple, dataclass, OR and guarded patterns."""
from dataclasses import dataclass


@dataclass
class Command:
    name: str
    value: int


def parse(text: str) -> Command:
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError("expected command:value")
    # Convert to a fixed tuple after the ordinary variable-length split check.
    match (parts[0], int(parts[1])):
        case ("add" | "sub", amount):
            return Command(parts[0], amount)
        case ("scale", factor) if factor > 0:
            return Command("scale", factor)
        case ("reset", 0):
            return Command("reset", 0)
        case (name, value):
            raise ValueError("invalid command: " + name + ":" + str(value))


def apply(total: int, command: Command) -> int:
    match command:
        case Command("add", amount):
            return total + amount
        case Command("sub", amount):
            return total - amount
        case Command("scale", factor) if factor > 0:
            return total * factor
        case Command(name="reset", value=0):
            return 0
        case _:
            raise ValueError("unsupported command")


def evaluate(commands: list[str]) -> list[int]:
    total = 0
    history: list[int] = []
    for text in commands:
        total = apply(total, parse(text))
        history.append(total)
    return history


if __name__ == "__main__":
    print(evaluate(["add:7", "sub:2", "scale:3", "reset:0", "add:-4"]))
    for text in ["scale:0", "reset:1", "unknown:3", "add"]:
        try:
            parse(text)
        except ValueError as error:
            print(str(error))
