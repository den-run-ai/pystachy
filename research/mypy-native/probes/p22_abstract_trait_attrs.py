# mypy/checker_shared.py: @trait TypeCheckerSharedApi declares attributes and abstract methods used through the trait type
from abc import abstractmethod
class Options:
    strict = True
class CheckerApi:
    options: Options
    @abstractmethod
    def fail(self, msg: str) -> None:
        raise NotImplementedError
class Visitor:
    def visit(self) -> str:
        return "v"
class TypeChecker(Visitor, CheckerApi):
    def __init__(self) -> None:
        self.options = Options()
        self.errors: list[str] = []
    def fail(self, msg: str) -> None:
        self.errors.append(msg)
def use(api: CheckerApi) -> bool:
    api.fail("x")
    return api.options.strict
c = TypeChecker()
print(use(c), c.errors)
