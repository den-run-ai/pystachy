# TOML's namespace flags have a closed recursive shape. Exercise their observable
# behavior through loads(): pending duplicates, recursive freezes and subtree reset.
import tomllib


def show(label: str, source: str) -> None:
    try:
        print(label, tomllib.loads(source))
    except tomllib.TOMLDecodeError as error:
        print(label, "TOMLDecodeError:", str(error))


# Both dotted keys add the same pending parent flags before the next header.
show("pending", "a.b.c = 1\na.b.d = 2\n[a.other]\nx = 3\n")
show("pending-reopen", "a.b.c = 1\na.b.d = 2\n[a.b]\nx = 3\n")
show("implicit-parent", "[a.b]\nx = 1\n[a]\ny = 2\n")
show("repeated-table", "[a]\nx = 1\n[a]\ny = 2\n")
show("redefined-dotted", "[a.b]\nx = 1\n[a]\nb.y = 2\n")
show("overwritten-leaf", "a = 1\n[a.b]\nx = 2\n")

# Freezing an inline table applies to every descendant namespace.
show("frozen-dotted", "a = {b = {c = 1}}\na.b.d = 2\n")
show("frozen-table", "a = {b = {c = 1}}\n[a.b.d]\nx = 2\n")
show("frozen-array", "a = [{b = 1}]\n[[a]]\nb = 2\n")

# A new array-of-tables element clears all flags below that element. The old
# element's inline table and pending dotted namespaces must not freeze the new one.
show("array-reset", """[[items]]
node.left = 1
node.right = 2
frozen = {child = {value = 3}}
[[items]]
[items.node]
left = 4
[items.frozen.child]
value = 5
""")
show("fresh-parse", "[a.b]\nc = 6\n")
