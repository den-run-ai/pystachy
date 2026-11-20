# error: unsupported base class: single inheritance requires a previously declared ordinary class or a supported exception class
class Tags(set):
    pass


print(len(Tags()))
