# error: reflect_fields_value.py:10: error: dataclasses.fields() is supported as the iterable of a for loop or a list comprehension
from dataclasses import dataclass, fields


@dataclass
class Item:
    name: str


fs = fields(Item)
print(len(fs))
