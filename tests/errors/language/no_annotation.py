# error: parameter 'x' of '__init__' needs a type annotation
# (an exception class is no class template: a handler cannot know which specialization it caught)
class Oops(Exception):
    def __init__(self, x) -> None:
        self.x = x


raise Oops(1)
