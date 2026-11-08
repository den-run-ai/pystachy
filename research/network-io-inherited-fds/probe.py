import sys

with open('/dev/fd/' + sys.argv[1], 'rb') as stream:
    print(stream.read(4).hex())
