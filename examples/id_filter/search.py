"""Faceted document filtering with reusable ID masks.

Run from the repository root:
    python3 examples/id_filter/search.py
    ./pystachy build examples/id_filter/search.py -o build/id-filter-search
    build/id-filter-search

Documents are (title, language, space-separated tags, blocked). IDs are stable
positions in this fixed document batch. Build a new index when the batch changes.
"""

from idset import IdSet


class SearchIndex:
    def __init__(self, documents: list[tuple[str, str, str, bool]]) -> None:
        n = len(documents)
        self.titles: list[str] = []
        self.tags: dict[str, IdSet] = {}
        languages: dict[str, IdSet] = {}
        blocked = IdSet(n)
        for value in range(n):
            title, language, tags, hidden = documents[value]
            self.titles.append(title)
            if language not in languages:
                languages[language] = IdSet(n)
            languages[language].add(value)
            for tag in tags.split():
                if tag not in self.tags:
                    self.tags[tag] = IdSet(n)
                self.tags[tag].add(value)
            if hidden:
                blocked.add(value)
        # Cache each eligible language once; repeated tag counts allocate no masks.
        self.allowed: dict[str, IdSet] = {}
        for language in languages:
            self.allowed[language] = languages[language].difference(blocked)

    def count(self, tag: str, language: str) -> int:
        if tag not in self.tags or language not in self.allowed:
            return 0
        return self.tags[tag].intersection_count(self.allowed[language])

    def matches(self, tag: str, language: str) -> list[str]:
        result: list[str] = []
        if tag in self.tags and language in self.allowed:
            ids = self.tags[tag].intersection(self.allowed[language]).ids()
            for value in ids:
                result.append(self.titles[value])
        return result


def sample_documents() -> list[tuple[str, str, str, bool]]:
    return [
        ("Native Python arrays", "en", "python numeric", False),
        ("Compiler internals", "en", "python compiler", False),
        ("Graph traversal", "en", "graph search", False),
        ("Draft compiler notes", "en", "python compiler", True),
        ("Tableaux numeriques", "fr", "python numeric", False),
        ("Vector search", "en", "numeric search", False),
        ("Python graph tools", "en", "python graph python", False),
        ("Recherche de graphes", "fr", "graph search", False),
    ]


def main() -> None:
    index = SearchIndex(sample_documents())
    for tag in ["python", "numeric", "graph", "search", "missing"]:
        print(tag, index.count(tag, "en"), index.matches(tag, "en"))


if __name__ == "__main__":
    main()
