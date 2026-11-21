# error: cannot infer what 'Stack' objects hold before an item is stored in one: name it in the base (class Stack(list[T]))
class Stack(list):
    pass


s = Stack()
print(s)
