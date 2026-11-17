from abc import abstractmethod


class Options:
    def __init__(self, level: int) -> None:
        self.level = level


class PluginApi:
    options: Options
    names: dict[str, int]

    @abstractmethod
    def fail(self, msg: str) -> None:
        raise NotImplementedError

    def level(self) -> int:
        return self.options.level + len(self.names)


def describe(api: PluginApi) -> str:
    api.names["seen"] = api.options.level
    return str(api.options.level) + ":" + ",".join(sorted(api.names))
