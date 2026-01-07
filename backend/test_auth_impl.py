from google.auth.credentials import Signing, Credentials

print("Signing abstract methods:", Signing.__abstractmethods__)
print("Credentials abstract methods:", Credentials.__abstractmethods__)

class TestImpl(Signing, Credentials):
    def refresh(self, request): pass
    def sign_bytes(self, message): pass
    @property
    def signer_email(self): return "test@example.com"
    @property
    def service_account_email(self): return "test@example.com"
    @property
    def signer(self): return "signer"

try:
    t = TestImpl()
    print("Instantiation successful")
except Exception as e:
    print("Instantiation failed:", e)
