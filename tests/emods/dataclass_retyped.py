from dataclasses import dataclass


@dataclass
class Point:
    x: int


@dataclass
class Retyped(Point):
    x: str = "r"


@dataclass
class Below(Retyped):
    z: int = 0
