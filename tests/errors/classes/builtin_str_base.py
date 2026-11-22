# error: unsupported base class: single inheritance requires a previously declared ordinary class or a supported exception class
class Name(str):
    def shout(self) -> str:
        return self.upper()


print(Name("a").shout())
