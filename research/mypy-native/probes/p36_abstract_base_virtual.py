from abc import ABC, abstractmethod
class Visitor(ABC):
    @abstractmethod
    def visit(self, n: int) -> str: ...
class V1(Visitor):
    def visit(self, n: int) -> str:
        return "v1:" + str(n)
def run(v: Visitor) -> str:
    return v.visit(3)
print(run(V1()))
