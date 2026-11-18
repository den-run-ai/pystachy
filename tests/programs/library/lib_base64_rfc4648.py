# The test vectors of RFC 4648, section 10
import base64

vectors = [(b"", b"", b"", b"", b""),
           (b"f", b"Zg==", b"MY======", b"CO======", b"66"),
           (b"fo", b"Zm8=", b"MZXQ====", b"CPNG====", b"666F"),
           (b"foo", b"Zm9v", b"MZXW6===", b"CPNMU===", b"666F6F"),
           (b"foob", b"Zm9vYg==", b"MZXW6YQ=", b"CPNMUOG=", b"666F6F62"),
           (b"fooba", b"Zm9vYmE=", b"MZXW6YTB", b"CPNMUOJ1", b"666F6F6261"),
           (b"foobar", b"Zm9vYmFy", b"MZXW6YTBOI======", b"CPNMUOJ1E8======", b"666F6F626172")]
for plain, b64, b32, b32hex, b16 in vectors:
    print(base64.b64encode(plain) == b64, base64.b64decode(b64) == plain,
          base64.b32encode(plain) == b32, base64.b32decode(b32) == plain,
          base64.b32hexencode(plain) == b32hex, base64.b32hexdecode(b32hex) == plain,
          base64.b16encode(plain) == b16, base64.b16decode(b16) == plain)
