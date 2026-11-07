# pystachy: dynamic-any
# Declined factory preparation must not awaken unrelated unsupported bodies.
from typing import Any
from registrymods.factory_only import ColdBody, ColdDispatch, ColdHelper, ColdNominal, ColdProtocol, Handler


class Ready:
    def __init__(self, value: int) -> None:
        self.value = value


def keep(value: int) -> int:
    return value + 1


# This adapter already exists; preparing ColdDispatch must not introduce a
# call.action dispatcher that compiles Handler.action outside its restart.
handler: Any = Handler(9)
# Preserve an independently accepted path: this case already ran before
# factory-only construction, without compiling the dormant imported bodies.
ready_seed: Any = Ready(0)
registry: dict[Any, Any] = {
    ColdBody: keep,
    ColdHelper: keep,
    ColdProtocol: keep,
    ColdNominal: keep,
    ColdDispatch: keep,
}
for key in registry:
    print(registry[key](10))
factory: Any = Ready
result = factory(7)
print(type(result) is Ready, result.value, handler.value)
