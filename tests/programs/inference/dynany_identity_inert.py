# pystachy: dynamic-any
import inert_scope

cursor = inert_scope.make("abc")
print(cursor.step("def"), cursor.step("gh"))
print(inert_scope.decode("1000"))
