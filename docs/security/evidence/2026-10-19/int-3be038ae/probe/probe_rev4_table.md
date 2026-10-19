# REV-4 probe on 3be038ae, with c66a5e61 as the control

In process, golden books, a fresh demo reset per message, BUYER-1's key. Outcome read from the ledger and approval queue: AUTO = ACCEPT_OFFER EXECUTED at Tier 1 without the owner. Script: `tools/probe_rev4.py` (the 7.3 tooling, new message list), run on both checkouts.

163 messages. Verdicts on 3be038ae: ok 118, BLOCKER 31, FALSE HOLD 14.

- **Blocker rule (REV-4 handoff, step 2):** any Tier-1 accept of a reversed-payer or quoted message. 31 such messages are still accepted alone; every one is also accepted alone on c66a5e61, so REV-4 leaves them as they were.
  - B2: 'You're able to pay', 'You'll pay', 'You'd pay', 'You'll settle' (the regex needs whitespace after 'you'; the contractions are filler); 'You, if ok, can pay', 'You can, if ok, pay', 'You - can pay', 'You: pay' (punctuation after 'you'); 'Thanks you can pay' (the look-behind skips it); 'You can do the payment of' ('payment' is not a pay verb); 你们，可以…, 你们 可以…, 贵司，… (a comma or space ends the Chinese window); 你们也可以就是想提前支付… (more than six characters to the verb).
  - B3: 'Hi, "…"' and 'Hi, “…”' (the quote does not start the line); '…', ‘…’, ＂…＂, «…», „…“, a ``` fence (characters not in the set; `_QUOTED` reads the raw, unfolded text); › ‹ │ ¦ 〉 《…》 (markers not in the set); a zero-width or non-breaking space before '>' (only spaces and tabs are allowed before the marker).
- **Caught by REV-4 (41 messages, all AUTO on c66a5e61, now QUEUED):** the writer's ten; U, YOU, you can settle, you pay, a newline or extra spaces after 'You', 'You can then pay', 'Thank you, you can pay', the homoglyphs 'Yοu' and 'Ｙｏｕ', 'pаy' with a Cyrillic а, 您/你/贵方, 付清/结清/付款; a quoted line in the middle or at the end, ＞, 》, 『』, “”, "", an indented '>'.
- **False holds:** none caused by REV-4. The 14 plain offers queued on 3be038ae are queued identically on c66a5e61 (they hold unread words such as 'like', 'agree', 'prefer', 'know', 'works', 'so much', 同意, 确认一下, 配合, 看).
- **Negations:** all 18 still held or queued.
- **Table 4 (autonomy funnel, held-out 3 and 2):** identical on both builds, row by row (funnel_*.json).

| # | Group | Message | 3be038ae | c66a5e61 | Verdict | Note |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | P writer's ten | You can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 1 | P writer's ten | You could pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 2 | P writer's ten | 你们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 3 | P writer's ten | 贵司可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 4 | P writer's ten | > We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 5 | P writer's ten | >> We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 6 | P writer's ten | » We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 7 | P writer's ten | \| We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 8 | P writer's ten | 「我们可以提前支付420,000元发票，折扣0.5%」 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 9 | P writer's ten | > 我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 10 | B2 second person | You guys can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 11 | B2 second person | Y'all can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 12 | B2 second person | Your side will pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 13 | B2 second person | You're able to pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 14 | B2 second person | You’re able to pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 15 | B2 second person | U can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 16 | B2 second person | YOU CAN PAY THE ¥420,000 INVOICE EARLY AT A 0.5% DISCOUNT. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 17 | B2 second person | You can settle the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 18 | B2 second person | You may pay the ¥420,000 invoice early at a 0.5% discount. | HELD | HELD | ok |  |
| 19 | B2 second person | You pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 20 | B2 second person | You'll pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 21 | B2 second person | You’ll pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 22 | B2 second person | You'd pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 23 | B2 second person | You'll settle the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 24 | B2 second person | You, if ok, can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 25 | B2 second person | You, if ok, will pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 26 | B2 second person | You - can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 27 | B2 second person | You: pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 28 | B2 second person | You⏎can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 29 | B2 second person | You  can   pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 30 | B2 second person | You can, if ok, pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 31 | B2 second person | You can do the payment of the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 32 | B2 second person | Your company can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 33 | B2 second person | Your accounts team can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 34 | B2 second person | Your finance team can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 35 | B2 second person | Your people can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 36 | B2 second person | Your CFO can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 37 | B2 second person | You and your team can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 38 | B2 second person | You yourselves can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 39 | B2 second person | You can then pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 40 | B2 second person | You can so pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 41 | B2 second person | Can you pay the ¥420,000 invoice early at a 0.5% discount? | QUEUED | QUEUED | ok |  |
| 42 | B2 second person | Could you pay the ¥420,000 invoice early at a 0.5% discount? | QUEUED | QUEUED | ok |  |
| 43 | B2 second person | Thank you, you can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 44 | B2 second person | Thanks you can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 45 | B2 second person | Thank you you can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 46 | B2 second person | Ya can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 47 | B2 second person | Yu can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 48 | B2 second person | Yοu can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 49 | B2 second person | Ｙｏｕ can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 50 | B2 second person | You can pаy the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 51 | B2 second person | It's you who can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 52 | B2 second person | The payer is you: pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 53 | B2 second person | 您们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 54 | B2 second person | 你方可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 55 | B2 second person | 贵单位可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 56 | B2 second person | 贵公司可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 57 | B2 second person | 贵方可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 58 | B2 second person | 你们可以付清420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 59 | B2 second person | 你们可以结清420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 60 | B2 second person | 你们可以结算420,000元发票，折扣0.5%。 | HELD | HELD | ok |  |
| 61 | B2 second person | 你们可以付款420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 62 | B2 second person | 你们，可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 63 | B2 second person | 你们 可以 提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 64 | B2 second person | 你们也可以就是想提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 65 | B2 second person | 您可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 66 | B2 second person | 你可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 67 | B2 second person | 你们明天付清420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 68 | B2 second person | 您好你们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 69 | B2 second person | 你们好，你们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 70 | B2 second person | 贵司，提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 71 | B2 second person | 由你们提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 72 | B2 second person | 你们去提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 73 | B2 second person | 請你們提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 74 | B3 quoting | We can pay the ¥420,000 invoice early at a 0.5% discount.⏎> earlier note | QUEUED | QUEUED | ok |  |
| 75 | B3 quoting | Hi,⏎> We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 76 | B3 quoting | We can pay the ¥420,000 invoice early at a 0.5% discount.⏎> Thanks | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 77 | B3 quoting | Re: We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 78 | B3 quoting | Fwd: We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 79 | B3 quoting | -----Original Message-----⏎We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 80 | B3 quoting | On Monday Li wrote:⏎We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 81 | B3 quoting | ＞ We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 82 | B3 quoting | 》 我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 83 | B3 quoting | 『我们可以提前支付420,000元发票，折扣0.5%』 | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 84 | B3 quoting | “We can pay the ¥420,000 invoice early at a 0.5% discount.” | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 85 | B3 quoting | "We can pay the ¥420,000 invoice early at a 0.5% discount." | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 86 | B3 quoting | "We can pay the ¥420,000 invoice early at a 0.5% discount."⏎Thanks, Li Wei | QUEUED | QUEUED | ok |  |
| 87 | B3 quoting | “We can pay the ¥420,000 invoice early at a 0.5% discount.”⏎Thanks! | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 88 | B3 quoting | Hi, "We can pay the ¥420,000 invoice early at a 0.5% discount." | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 89 | B3 quoting | Hi, “We can pay the ¥420,000 invoice early at a 0.5% discount.” | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 90 | B3 quoting | 'We can pay the ¥420,000 invoice early at a 0.5% discount.' | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 91 | B3 quoting | ‘We can pay the ¥420,000 invoice early at a 0.5% discount.’ | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 92 | B3 quoting | ＂We can pay the ¥420,000 invoice early at a 0.5% discount.＂ | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 93 | B3 quoting | › We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 94 | B3 quoting | ‹ We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 95 | B3 quoting | │ We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 96 | B3 quoting | ¦ We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 97 | B3 quoting | 〉 We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 98 | B3 quoting | 《我们可以提前支付420,000元发票，折扣0.5%》 | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 99 | B3 quoting |   > We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 100 | B3 quoting | 	> We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 101 | B3 quoting | ​> We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 102 | B3 quoting |  > We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 103 | B3 quoting | Thanks!⏎> We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | AUTO | ok | REV-4 changed AUTO to QUEUED |
| 104 | B3 quoting | We said: "We can pay the ¥420,000 invoice early at a 0.5% discount." | QUEUED | QUEUED | ok |  |
| 105 | B3 quoting | «We can pay the ¥420,000 invoice early at a 0.5% discount.» | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 106 | B3 quoting | „We can pay the ¥420,000 invoice early at a 0.5% discount.“ | AUTO | AUTO | BLOCKER | also accepted alone on c66a5e61; REV-4 does not catch it |
| 107 | B3 quoting | ```⏎We can pay the ¥420,000 invoice early at a 0.5% discount.⏎``` | AUTO | AUTO | BLOCKER | weaker quote convention; also accepted alone on c66a5e61; REV-4 does not catch it |
| 108 | B3 quoting | 我们可以提前支付420,000元发票，折扣0.5%。⏎——转发—— | QUEUED | QUEUED | ok |  |
| 109 | OK plain offer | We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 110 | OK plain offer | We will pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 111 | OK plain offer | We would like to pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 112 | OK plain offer | Can we pay the ¥420,000 invoice early at a 0.5% discount? | AUTO | AUTO | ok |  |
| 113 | OK plain offer | Hi, we can pay the ¥420,000 invoice early at a 0.5% discount. Thanks! | AUTO | AUTO | ok |  |
| 114 | OK plain offer | Thank you, we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 115 | OK plain offer | Thank you we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 116 | OK plain offer | If you agree we can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 117 | OK plain offer | If you agree, we can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 118 | OK plain offer | Could you confirm, we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 119 | OK plain offer | Please confirm: we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 120 | OK plain offer | We can pay you the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 121 | OK plain offer | Can we pay you the ¥420,000 invoice early at a 0.5% discount? | AUTO | AUTO | ok |  |
| 122 | OK plain offer | Hope you are well, we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 123 | OK plain offer | Hope you are well we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 124 | OK plain offer | Thanks to you we can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 125 | OK plain offer | If you prefer we can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 126 | OK plain offer | As you know, we can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 127 | OK plain offer | We can pay the ¥420,000 invoice early at a 0.5% discount, if that works for you. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 128 | OK plain offer | Let us know if you agree. We can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 129 | OK plain offer | Thank you so much, we can pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 130 | OK plain offer | Thanks! We can pay the ¥420,000 invoice early at a 0.5% discount. | AUTO | AUTO | ok |  |
| 131 | OK plain offer | 我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 132 | OK plain offer | 您好，我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 133 | OK plain offer | 您好我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 134 | OK plain offer | 谢谢你们，我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 135 | OK plain offer | 感谢贵司，我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 136 | OK plain offer | 如果你们同意，我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 137 | OK plain offer | 如果你们同意我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 138 | OK plain offer | 请您确认，我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 139 | OK plain offer | 麻烦您确认一下，我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 140 | OK plain offer | 我们可以付清420,000元发票，提前付款，折扣0.5%。 | AUTO | AUTO | ok |  |
| 141 | OK plain offer | 谢谢您，我们可以提前支付420,000元发票，折扣0.5%。 | AUTO | AUTO | ok |  |
| 142 | OK plain offer | 感谢您的配合，我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 143 | OK plain offer | 您看我们可以提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 144 | OK plain offer | 你们看我们提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | FALSE HOLD | also queued on c66a5e61 (not caused by REV-4) |
| 145 | N negation | We won't pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 146 | N negation | We can't pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 147 | N negation | We cannot pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 148 | N negation | We will never pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 149 | N negation | We are unable to pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 150 | N negation | We refuse to pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 151 | N negation | We wouldn't pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 152 | N negation | We couldn't pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 153 | N negation | We decline to pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 154 | N negation | We are not able to pay the ¥420,000 invoice early at a 0.5% discount. | QUEUED | QUEUED | ok |  |
| 155 | N negation | 我们不会提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 156 | N negation | 我们不能提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 157 | N negation | 我们无法提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 158 | N negation | 我们没法提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 159 | N negation | 我们不可能提前支付420,000元发票，折扣0.5%。 | HELD | HELD | ok |  |
| 160 | N negation | 我们拒绝提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 161 | N negation | 我们不打算提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
| 162 | N negation | 我们不愿意提前支付420,000元发票，折扣0.5%。 | QUEUED | QUEUED | ok |  |
