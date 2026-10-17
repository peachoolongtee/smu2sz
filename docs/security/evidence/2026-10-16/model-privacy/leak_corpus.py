"""Adversarial leak corpus against app.compiler.redaction (no network)."""
import re
from collections import defaultdict
from app.compiler.redaction import Redactor

C = [  # (category, text, sensitive value)
 # names (by design not redacted)
 ("person name", "联系人：张伟，请尽快回复。", "张伟"),
 ("person name", "法定代表人：王小明", "王小明"),
 ("person name", "Contact: John Smith, Finance Director", "John Smith"),
 ("person name", "Attn: Zhang Wei (finance)", "Zhang Wei"),
 ("person name", "经办人 欧阳娜娜 签字", "欧阳娜娜"),
 ("person name", "Signed: Li Xiaoming", "Li Xiaoming"),
 # phones
 ("phone", "请致电 +86 138 0013 8000 联系我们", "+86 138 0013 8000"),
 ("phone", "请联系13800138000", "13800138000"),
 ("phone", "电话：(021) 5555-1234", "(021) 5555-1234"),
 ("phone", "call (021) 5555-1234 today", "(021) 5555-1234"),
 ("phone", "手机：１３８００１３８０００", "１３８００１３８０００"),
 ("phone", "call 138-0013-8000", "138-0013-8000"),
 ("phone", "call +86-138-0013-8000", "+86-138-0013-8000"),
 ("phone", "办公室 0755-8888 6666", "0755-8888 6666"),
 ("phone", "call 021 5555 1234", "021 5555 1234"),
 ("phone", "客服 400-820-8820", "400-820-8820"),
 ("phone", "call +1 (415) 555-0132", "+1 (415) 555-0132"),
 ("phone", "London office +44 20 7946 0958", "+44 20 7946 0958"),
 ("phone", "电话：(0755)86001234", "(0755)86001234"),
 ("phone", "Tel: +86 (755) 8600 1234", "+86 (755) 8600 1234"),
 ("phone", "WhatsApp: +852 9123 4567", "+852 9123 4567"),
 ("phone", "Phone: 138.0013.8000", "138.0013.8000"),
 ("phone", "联系号码：13800138000", "13800138000"),
 ("phone", "Contact number: 13800138000", "13800138000"),
 ("phone", "WhatsApp number +852 9123 4567", "+852 9123 4567"),
 ("phone", "Mob 13800138000", "13800138000"),
 ("phone", "微信/手机同号13800138000", "13800138000"),
 ("phone", "HK mobile 9123 4567", "9123 4567"),
 # emails
 ("email", "Reply to zhang.wei@example.com please", "zhang.wei@example.com"),
 ("email", "邮箱zhang@sz-precision.cn", "zhang@sz-precision.cn"),
 ("email", "wei_zhang+invoices@mail.sz-precision.com.cn", "wei_zhang+invoices@mail.sz-precision.com.cn"),
 ("email", "邮箱：zhangwei＠example.com", "zhangwei＠example.com"),
 ("email", "write to zhang wei at example dot com", "zhang wei at example dot com"),
 ("email", "联系 张伟@公司.中国", "张伟@公司.中国"),
 ("email", "mailto:finance@buyer.co.uk", "finance@buyer.co.uk"),
 # national id / passport
 ("national ID", "110101199003074578 is my ID", "110101199003074578"),
 ("national ID", "身份证号：11010119900307457X", "11010119900307457X"),
 ("national ID", "居民身份证号码 11010119900307457x", "11010119900307457x"),
 ("national ID", "ID 1101 0119 9003 0745 78", "1101 0119 9003 0745 78"),
 ("national ID", "身份证：１１０１０１１９９００３０７４５７８", "１１０１０１１９９００３０７４５７８"),
 ("national ID", "旧身份证 110101900307457", "110101900307457"),
 ("national ID", "HKID A123456(7)", "A123456(7)"),
 ("passport", "Passport No.: E12345678", "E12345678"),
 ("passport", "护照号码：E12345678", "E12345678"),
 ("passport", "passport E12345678", "E12345678"),
 ("passport", "Passport Number: G12345678", "G12345678"),
 # bank accounts
 ("bank account", "卡号 6222 0212 3456 7890 123", "6222 0212 3456 7890 123"),
 ("bank account", "pay to 6222021234567890123", "6222021234567890123"),
 ("bank account", "pay to 6222-0212-3456-7890", "6222-0212-3456-7890"),
 ("bank account", "开户行：中国工商银行深圳南山支行 账号：4000023409200123456", "4000023409200123456"),
 ("bank account", "开户银行：招商银行 帐号 755912345610801", "755912345610801"),
 ("bank account", "收款账户信息：招商银行 755912345610801", "755912345610801"),
 ("bank account", "Beneficiary account: 755912345610801", "755912345610801"),
 ("bank account", "A/C 755912345610801", "755912345610801"),
 ("bank account", "IBAN GB82 WEST 1234 5698 7654 32", "GB82 WEST 1234 5698 7654 32"),
 ("bank account", "IBAN: DE89370400440532013000", "DE89370400440532013000"),
 ("bank account", "Card No. 4111 1111 1111 1111", "4111 1111 1111 1111"),
 ("bank account", "收款账号为6222021234567890123", "6222021234567890123"),
 ("bank account", "账号：６２２２０２１２３４５６７８９０１２３", "６２２２０２１２３４５６７８９０１２３"),
 ("bank account", "Bank account number 6222021234567890123", "6222021234567890123"),
 ("bank account", "acct 12-3456-7890123", "12-3456-7890123"),
 ("bank account", "Payment ref: 6222021234567890123", "6222021234567890123"),
 # USCC
 ("USCC", "统一社会信用代码：91310000MA1FL1234B", "91310000MA1FL1234B"),
 ("USCC", "公司 91310000MA1FL1234B 盖章", "91310000MA1FL1234B"),
 ("USCC", "credit code 91310000ma1fl1234b", "91310000ma1fl1234b"),
 ("USCC", "信用代码 9131 0000 MA1F L123 4B", "9131 0000 MA1F L123 4B"),
 ("USCC", "营业执照注册号 440301103456789", "440301103456789"),
 # addresses
 ("address", "地址：深圳市南山区科技园科苑路15号", "深圳市南山区科技园科苑路15号"),
 ("address", "我们在深圳市南山区科技园科苑路15号", "深圳市南山区科技园科苑路15号"),
 ("address", "Address: 88 Queen's Road Central, Hong Kong", "88 Queen's Road Central"),
 ("address", "we are located at 88 Queen's Road Central, Hong Kong", "88 Queen's Road Central"),
 ("address", "收货地址 北京市朝阳区建国路88号", "北京市朝阳区建国路88号"),
 ("address", "住址：上海市徐汇区漕溪北路1200弄3号601室", "上海市徐汇区漕溪北路1200弄3号601室"),
 ("address", "Ship to: 1 Main Street, Springfield", "1 Main Street"),
 ("address", "邮编 518057", "518057"),
 # wechat / other handles
 ("WeChat/QQ", "微信：zhangwei_88", "zhangwei_88"),
 ("WeChat/QQ", "WeChat ID: wxid_abc123xyz", "wxid_abc123xyz"),
 ("WeChat/QQ", "QQ: 123456789", "123456789"),
 # company names (by design kept)
 ("company name", "买方：深圳市南山精密制造有限公司", "深圳市南山精密制造有限公司"),
 ("company name", "Buyer: Foshan Home Retail Co., Ltd.", "Foshan Home Retail Co., Ltd."),
]

def chunks(v):
    return [c for c in re.split(r"[ \-().＠@]+", v) if len(c) >= 4]

tot = defaultdict(lambda: [0, 0, 0, []])
for cat, text, v in C:
    r = Redactor().redact(text)
    red = r.redacted
    full = v in red
    part = (not full) and any(c in red for c in chunks(v))
    t = tot[cat]; t[0] += 1
    if full: t[1] += 1
    if part: t[2] += 1
    flag = "LEAK" if full else ("PART" if part else "ok  ")
    print(f"{flag} {cat:13} {text!r} -> {red!r}")
print()
print(f"{'category':14} total full_leak partial")
for cat, (n, f, p, _) in tot.items():
    print(f"{cat:14} {n:5} {f:9} {p:7}")
