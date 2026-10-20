# HTMLParser columns count code points, including after a newline.
from html.parser import HTMLParser
p = HTMLParser()
p.feed('éπ')
print(p.getpos())
p.feed('\nç')
print(p.getpos())
