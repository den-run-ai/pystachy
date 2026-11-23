# Forwarding through several calls: api passes its parameter to loads, which passes it on to
# repair, and a method passes its own to api; each is compiled for each literal it is given.
class Client:
    def fetch(self, s: str, raw: bool = False):
        return api(s, raw)


def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


def loads(s: str, logging: bool = False):
    return repair(s, logging)


def api(s: str, verbose: bool = False):
    return loads(s, logging=verbose)


c = Client()
print(api("a"), api("b", True), c.fetch("c"), c.fetch("d", raw=True))
