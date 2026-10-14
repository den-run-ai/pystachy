# Pystachy HTMLParser reports UTF-8 byte columns, not Unicode character columns.
from html.parser import HTMLParser
p = HTMLParser()
p.feed('éπ')
print(p.getpos())
p.feed('\nç')
print(p.getpos())
