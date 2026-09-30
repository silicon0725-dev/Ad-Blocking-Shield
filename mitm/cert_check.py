# 通过 8080 代理 CONNECT 后检查对端证书颁发者, 判断是否被 MITM
import socket
import ssl
import sys

host = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
s = socket.create_connection(("127.0.0.1", port), timeout=10)
s.sendall(("CONNECT %s:443 HTTP/1.1\r\nHost: %s\r\n\r\n" % (host, host)).encode())
buf = b""
while b"\r\n\r\n" not in buf:
    buf += s.recv(4096)
assert b" 200 " in buf.split(b"\r\n")[0], buf[:100]

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
tls = ctx.wrap_socket(s, server_hostname=host)
cert = tls.getpeercert(binary_form=False) or {}
der = tls.getpeercert(binary_form=True)
import hashlib
print(host, "sha256前8:", hashlib.sha256(der).hexdigest()[:8])
# binary form 时 dict 为空, 用 ssl._ssl 解析
c2 = ssl.create_default_context()
c2.check_hostname = False
c2.verify_mode = ssl.CERT_NONE
# 直接从 DER 提取 issuer: 用 ssl.DER_cert_to_PEM_cert + openssl 不在; 用 cryptography
from cryptography import x509
crt = x509.load_der_x509_certificate(der)
print("  issuer :", crt.issuer.rfc4514_string())
print("  subject:", crt.subject.rfc4514_string()[:80])
print("  有效期 :", crt.not_valid_before_utc, "→", crt.not_valid_after_utc)
tls.close()
