from app.compiler.redaction import Redactor
for t in [
 "交货地址：广东省佛山市顺德区北滘镇工业大道1号，交货期为合同签订后30日内，买方于验收合格后45日内付款。",
 "The Supplier shall deliver the Goods to the Buyer's address at 12 Keyuan Road within thirty (30) days of each Purchase Order.",
 "The Supplier shall deliver to the address at Unit 5, 88 Industrial Ave, Foshan, payment due 45 days after invoice",
 "Address: 1 Main St, Shenzhen; Payment: 45 days after invoice",
 "开户行：中国银行佛山分行，账号：7123 4567 8901 2345 678，付款期限：发票后45天。",
 "乙方账户：62220212345678901 23（人民币）",
]:
    print(repr(t), "\n   ->", repr(Redactor().redact(t).redacted))
