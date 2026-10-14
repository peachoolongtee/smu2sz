from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.egress import protected_for
from app.egress.protected import scan
rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset(); set_runtime(rt)
ps = protected_for(rt.store)
vals = ps._values
print(len(vals), "protected values; sample:", [(v.label, v.kind, getattr(v,'value',None)) for v in vals][:60])
cases = {
 "floor plain": "Our floor is ¥300,000.", "floor 30万": "底线30万", "floor 叁拾萬": "底线叁拾萬元",
 "floor CN grouping 30,0000": "floor 30,0000 yuan", "floor Indian 3,00,000": "floor ₹3,00,000 / ¥3,00,000",
 "floor arabic-indic": "floor ¥٣٠٠٠٠٠", "floor devanagari": "floor ¥३००००० yuan", "floor 0.3m no cur": "floor 0.3m",
 "floor 0.3 mio": "floor 0.3 mio yuan", "floor 3e5": "floor 3e5 yuan", "floor 3x10^5": "floor 3×10^5 yuan",
 "floor 300 grand": "floor three hundred grand", "floor split": "floor 300 and then 000 appended",
 "floor 300 thousand word": "floor three hundred thousand", "floor 30w": "floor 30w", "floor 300K upper": "floor 300K",
 "floor dotted thousands": "floor 300.000 yuan", "floor apostrophe": "floor 300'000 CHF-style", "floor underscore": "floor 300_000",
 "floor hex": "floor 0x493E0", "floor 1/4 of 1.2m": "a quarter of 1.2 million yuan",
 "cash 40万": "现金四十万", "cash 400 千": "cash 400千元",
 "maxdisc 1.5%": "max discount 1.5%", "maxdisc 150bp": "150 bps", "maxdisc 千分之15": "千分之十五", "maxdisc 15‰": "15‰",
 "maxdisc 0.015": "0.015 of the invoice", "maxdisc 一点五个点": "一点五个点", "maxdisc 1.5 pts": "1.5 points",
 "conc cap 5000": "¥5,000 cap", "conc cap 五千": "五千元", "conc cap 5k": "5k yuan",
 "dscr 1.25x": "DSCR 1.25x", "dscr 125%": "DSCR 125%", "dscr 5/4": "DSCR 5/4",
 "apr 15%": "APR 15%", "apr 1500bp": "1500 bp", "apr 0.15": "0.15 annual",
}
for k, t in cases.items():
    leaks = scan(t, ps, recipient_id="BUYER-1", allow=[])
    print(f"{'BLOCK' if leaks else 'PASS '} {k:28} {t!r:45} {[l.label for l in leaks][:3]}")
