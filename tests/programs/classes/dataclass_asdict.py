# dataclasses.asdict() (#486): a dict of the fields, made for the class
from dataclasses import asdict, dataclass


@dataclass
class P:
    x: int


print(asdict(P(1)))
