# A field assigned from a parameter's method result or a module constant: "cannot infer the type
# of field ...; annotate it" until the field is annotated (self.platform: bytes = ...)
LIMIT = 202


class Options:
    def __init__(self, platform: str) -> None:
        self.platform = platform.encode()
        self.depth = LIMIT


print(Options("linux").platform, Options("x").depth)
