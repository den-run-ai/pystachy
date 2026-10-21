class Account:
    def __init__(self, owner: str, balance: int) -> None:
        self.owner = owner
        self.balance = balance

    @property
    def balance(self) -> int:
        return self._cents // 100

    @balance.setter
    def balance(self, value: int) -> None:
        if value < 0:
            raise ValueError(f"negative balance for {self.owner}")
        self._cents = value * 100

    @balance.deleter
    def balance(self) -> None:
        self._cents = 0


class Savings(Account):
    @Account.balance.setter
    def balance(self, value: int) -> None:
        self._cents = max(value, 10) * 100
