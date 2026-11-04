# error: syntax_private_name_parameter.py:5: error: duplicate argument '_C__value' in function definition
class C:
    def method(self,
               __value,
               _C__value):
        pass
