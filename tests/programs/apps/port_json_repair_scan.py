from json_repair.json_parser import JSONParser


# The list-target path retains upstream's scanner and is an independent oracle
# for the string-search path, including scans starting inside escape runs.
checks = 0
for text in ["", 'a"b', 'a\\"b"', 'a\\\\"b"', 'a\\\\\\"b"', 'a”b\\”c”', 'é😀"z']:
    parser = JSONParser(text, False)
    for target in ['"', '”', '\\', '', 'ab']:
        for index in range(len(text) + 1):
            parser.index = index
            for start in range(-min(len(text), 2), len(text) + 2):
                offset = start - index
                assert parser.skip_to_character(target, offset) == parser.skip_to_character([target], offset)
                checks += 1
print("scanner comparisons", checks)
