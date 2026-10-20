class C:
    def __len__(self) -> int:
        return -1


print("yes" if C() else "no")
