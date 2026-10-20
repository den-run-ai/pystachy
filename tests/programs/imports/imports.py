from __future__ import annotations
import sys
import os.path
import math as m
from math import sqrt, pi, floor as fl
from os import path
from sys import argv, exit
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class Node:
    val: int
    nxt: Optional[Node] = None


def norm(xs: List[float]) -> float:
    return sqrt(sum([x * x for x in xs]))


counts: Dict[str, int] = {"a": 1}
print(norm([3.0, 4.0]), round(pi, 5), fl(2.7), m.ceil(2.1), m.e)
print(len(argv), argv[1:], path.exists("/"), os.path.exists("/no/such/file"))
print(Node(1, Node(2)), counts)
sys.stdout.write("done\n")
exit(3)
