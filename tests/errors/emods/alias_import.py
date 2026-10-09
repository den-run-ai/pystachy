from dataclasses import dataclass


def mine(c):
    print("mine", c.__name__)
    return c


dataclass = mine


@dataclass
class Job:
    retries: int
