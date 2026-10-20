# error: class_template_rebind.py:9: error: expected Box[int], got Box[str]
# each specialization is a type of its own, and a variable holds one type
class Box:
    def __init__(self, v):
        self.v = v


b = Box(1)
b = Box("s")
print(b.v)
