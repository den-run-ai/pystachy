# error: 'urllib.parse.SplitResult' object has no attribute 'hostname'
# (username, password, hostname and port are properties of CPython's mixins, which Pystachy does not compile)
from urllib.parse import urlsplit

print(urlsplit("http://user@Example.com:8080/").hostname)
