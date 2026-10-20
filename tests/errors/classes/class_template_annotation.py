# error: class_template_annotation.py:12: error: class Box is a class template (its __init__ takes a parameter without an annotation): each call makes an object of a specialization of its own, which an annotation cannot name here; leave the annotation out
from dataclasses import dataclass


class Box:
    def __init__(self, v):
        self.v = v


@dataclass
class Shelf:
    box: Box


print(Shelf(Box(1)))
