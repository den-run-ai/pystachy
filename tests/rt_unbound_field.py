class Conn:
    def __init__(self, host: str, port: int):
        self.host = host
        if port > 0:
            self.port = port

    def url(self) -> str:
        return f"{self.host}:{self.port}"


print(Conn("a", 80).url())
print(Conn("b", 0).url())
