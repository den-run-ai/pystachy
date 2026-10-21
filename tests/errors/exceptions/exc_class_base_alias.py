# error: unsupported base class: single inheritance requires a previously declared ordinary class or a supported exception class
VE = ValueError


class E(VE):
    pass
