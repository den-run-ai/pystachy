# error: expected bytes, got str
import librt.base64

print(librt.base64.urlsafe_b64encode("text"))
