# error: Job, a class template that derives from another class, is not supported for an argument of type
# Each specialization of a class template under an ordinary class is made where the classes are
# declared, before any code is compiled (#962), and so for the types that the declarations know:
# not a lambda's, which only compiled code makes.
class Task:
    def __init__(self) -> None:
        self.done = False


class Job(Task):
    def __init__(self, action):
        super().__init__()
        self.action = action


print(Job(lambda: 1).done)
