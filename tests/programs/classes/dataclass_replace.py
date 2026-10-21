# dataclasses.replace(): a new object made by the class's __init__ from the changes and the
# other init=True fields; init=False fields are made again, and __post_init__ runs again.
import dataclasses
from dataclasses import dataclass, field, replace


def arg(label: str, v: int) -> int:
    print("arg", label)
    return v


@dataclass(frozen=True)
class Settings:
    host: str
    port: int = 80
    paths: list[str] = field(default_factory=list)
    hits: list[int] = field(init=False, default_factory=lambda: [0])
    _: dataclasses.KW_ONLY
    debug: bool = False

    def __post_init__(self) -> None:
        print("post_init", self.host, self.port)


s = Settings("example.org")
t = replace(s, port=arg("port", 8080), debug=True)
u = dataclasses.replace(t, host="ünïcode.example")
print(s, t, u, sep="\n")
print(s.paths is t.paths, s.hits is t.hits, s == replace(s))


@dataclass
class Node:
    name: str
    children: list["Node"] = field(default_factory=list)


root = Node("root", [Node("leaf")])
copy = replace(root, name="copy")
copy.children.append(Node("added"))
print(root, copy.name, len(root.children))


def rename(n: Node | None, name: str) -> Node:
    return replace(n, name=name)


print(rename(root, "renamed").name)
try:
    rename(None, "x")
except TypeError as e:
    print("TypeError", e)
