"""certify_language_boundary LiveMode with offline (fake) providers: what reaches the 'provider'."""
import sys, importlib.util, pathlib
root = pathlib.Path.cwd().parents[1]
spec = importlib.util.spec_from_file_location("cert", root / "scripts" / "certify_language_boundary.py")
cert = importlib.util.module_from_spec(spec); sys.modules["cert"] = cert; spec.loader.exec_module(cert)
from app.domain.models import SourceDocument
seen = []
class Resp:
    def __init__(self): self.content=[]; self.stop_reason="end_turn"; self.model="fake"
class Msgs:
    def create(self, **kw): seen.append(("compile", kw["messages"][0]["content"])); raise RuntimeError("offline")
class Beta: messages = Msgs()
class Client: beta = Beta()
def complete(system, user, schema): seen.append(("classify", user)); raise TimeoutError("offline")
m = cert.LiveMode(allow_single_provider=True, offline={"claude": {"client": Client(), "complete": complete}})
log = cert.Log()
comp, clf = m.chains({}, "primary", log)
doc = SourceDocument(doc_id="D1", channel="email", sender_id="B", received_day=1,
                     text="Pay 2% early on INV-2026-0871. Remit to 账号：6222021234567890123, call 13800138000.")
for b in comp[:-1]:
    try: b.extract_offer([doc])
    except Exception as e: pass
for c in clf:
    try: c.classify("call me on 13800138000")
    except Exception: pass
for kind, text in seen:
    print(kind, "raw account/phone reached provider:", "6222021234567890123" in text or "13800138000" in text)
print("backends:", [type(getattr(b, "inner", b)).__name__ for b in comp], [type(getattr(c, "inner", c)).__name__ for c in clf])
