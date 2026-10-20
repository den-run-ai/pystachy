# error: class_template_nesting.py:8: error: Box() needs more than 100 nested template functions; annotate its parameters
# each call makes a specialization holding the one before, Box(Box(Box(...))), without end
class Box:
    def __init__(self, v):
        self.v = v

    def nest(self):
        return Box(self).nest()


print(Box(1).nest())
