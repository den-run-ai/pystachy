print("noisy: imported")


class P:
    @property
    def value(self):
        print("noisy: property read")
        return 7

    def __str__(self):
        print("noisy: __str__")
        return "P"

    def __len__(self):
        print("noisy: __len__")
        return 3
