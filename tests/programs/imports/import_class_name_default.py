# A method default reads the class body's own __name__ constant (once rejected).
from emods.class_name import Named

print(Named().name())
