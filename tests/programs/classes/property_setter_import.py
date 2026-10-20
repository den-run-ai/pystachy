import property_setter_mod
from mods.accounts import Rounded
from property_setter_mod import Account, Savings
from property_setter_mod import Account as Acct

a = Account("Zoë", 5)
a.balance += 7
print(a.owner, a.balance)
del a.balance
print(a.balance)
try:
    a.balance = -1
except ValueError as e:
    print("caught", e)
s = property_setter_mod.Savings("Ann", 1)
print(s.balance)
s.balance = 50
print(s.balance)
accounts: list[Account] = [a, s, Savings("Bo", 20)]
for x in accounts:
    x.balance = 3
    print(x.balance)


# @Base.x.setter, with Base another module's class (imported, aliased, or the module's attribute)
class Capped(Account):
    @property_setter_mod.Account.balance.setter
    def balance(self, value: int) -> None:
        self._cents = min(value, 99) * 100


class Doubled(property_setter_mod.Account):
    @Acct.balance.setter
    def balance(self, value: int) -> None:
        self._cents = value * 200


c = Capped("Ćelik", 500)
d = Doubled("Dee", 2)
print(c.balance, d.balance)
more: list[Account] = [c, d, Account("Eve", 1), Rounded("Rö", 57)]
for x in more:
    x.balance += 1
    print(x.owner, x.balance)
del d.balance
print(d.balance)
