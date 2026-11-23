# A class template under an ordinary class (#962): Child's specializations derive from Base. Inside
# its own __init__, Child names the current specialization, as the annotation of next does.
class Base:
    pass


class Child(Base):
    def __init__(self, value):
        self.data = value
        self.next: Child | None = None


c = Child(1)
c.next = Child(2)
print(c.data, c.next.data if c.next is not None else None, isinstance(c, Base))
