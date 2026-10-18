"""Deterministic lexicon (en + zh) for owner intents, and exact parsers for money, rates and days.

Amounts come out as integer fen and rates as integer bp, parsed with Decimal; anything with sub-fen
or sub-bp precision is ignored rather than rounded (INVARIANT 9).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.compiler.parsing import find_rates, rx
from app.domain.models import FinancialState


def norm(text: str) -> str:
    """NFKC (full-width digits and ％ become ASCII) and lower case."""
    return unicodedata.normalize("NFKC", text).lower()


def detect_lang(text: str) -> str:
    cjk = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "zh" if cjk > 0 and cjk * 2 >= latin else "en"


def _re(*parts: str) -> re.Pattern[str]:
    """Alternatives, case-insensitive, with CJK-safe word boundaries (EV-08: "批准APR-000003")."""
    return rx("|".join(parts), re.IGNORECASE)


# ---------------------------------------------------------------- intent cues

CORRECTION = _re(r"\bactually\b", r"\binstead\b", r"\bmake (?:it|that)\b", r"\bchange (?:it|that|the rate) to\b",
                 r"\bswitch to\b", r"\brather\b", r"改成", r"改为", r"换成", r"其实", r"改用", r"不如用")
CONFIRM = _re(r"^\s*(?:yes|yep|yeah|ok(?:ay)?|sure|go ahead|proceed|confirm(?:ed)?|do it|lgtm|execute|run it)\b",
              r"\bgo ahead\b", r"\bapprove[ds]?\b", r"\bconfirm\b", r"批准", r"同意", r"确认", r"^\s*执行", r"^\s*好的?",
              r"就这么办", r"可以执行", r"办吧", r"照办", r"去办", r"^\s*行(?:吧|的)?\s*[。!！]?\s*$", r"^\s*可以\s*[。!！]?\s*$")
# A confirmation that names nothing ("yes do it", "好的办吧"): it can only bind to what this session just showed.
BARE_CONFIRM = _re(r"^\s*(?:yes|yep|yeah|ya|ok(?:ay)?|sure|go ahead|proceed|do it|lgtm|execute|run it|confirm(?:ed)?|fine|alright)"
                   r"(?:[\s,.!]+(?:yes|please|pls|do it|go ahead|go|proceed|then|now|thanks?|sure|ok))*[\s.!]*$",
                   r"^\s*(?:好的?|行|可以|同意|确认|执行|没问题)(?:的|吧|啊|呀)?[，,。.!！\s]*(?:办吧|就这么办|去办|照办|执行吧?|做吧|弄吧)?[。.!！\s]*$",
                   r"^\s*(?:就这么办|照办|办吧|执行吧)[。.!！\s]*$")
APPROVE_VERB = _re(r"\bapprove[ds]?\b", r"批准", r"审批通过")
DECLINE = _re(r"^\s*(?:no|nope|cancel|stop|abort|don'?t|do not)\b", r"\breject\b", r"\bdecline\b", r"\bdeny\b",
              r"\bcancel\b", r"驳回", r"拒绝", r"取消", r"^\s*不要", r"算了")
EXECUTE_NOW = _re(r"\bnow\b", r"\bright away\b", r"\bimmediately\b", r"\bgo ahead and\b", r"\band do it\b",
                  r"立即", r"马上", r"现在就", r"立刻")
# A question about a term itself ("what does 'break-even discount' actually mean", 贴息是什么意思)
_GLOSSARY_Q = (r"\bwhat\s+(?:does|do)\s+(?!it\b|that\b|this\b|they\b)['\"“‘]?[\w\s/-]{2,40}?['\"”’]?\s+(?:actually\s+|really\s+|even\s+)?mean\b"
               r"|\bwhat(?:'s| is| are)\s+(?:an?\s+|the\s+)?['\"“‘][\w\s/-]{2,40}['\"”’]|\bmeaning\s+of\b|\bdefine\b"
               r"|是什么意思|什么意思|啥意思|什么叫|何谓")
GLOSSARY = _re(_GLOSSARY_Q)
EXPLAIN = _re(r"\bwhy\b", r"\bexplain\b", r"\bhow come\b", r"\breasons?\b", r"为什么", r"为何", r"解释", r"原因", r"依据",
              _GLOSSARY_Q)
WHAT_IF = _re(r"\bwhat if\b", r"\bwhat would happen\b", r"\bwhat happens\b", r"\bsuppose\b", r"\bhypothetical",
              r"\bwhat (?:would|will|does) (?:it|that) (?:do|mean|look like|cost)\b",
              r"\bhow (?:would|will|does)\b.{0,50}\b(?:affect|change|impact|hit)\b", r"\bimpact of\b",
              r"如果", r"假如", r"假设", r"要是", r"会怎样", r"会怎么样", r"会如何", r"有什么影响", r"影响多大",
              # the cost of a change to a buyer's terms: "给佛山60天账期要花我们多少钱", "把佛山账期延到60天成本多少"
              r"(?:给|延|延长|延到|改|改成|放宽|放到)[^，。?？]{0,10}账期[^，。?？]{0,12}(?:要花|花|成本|代价|多少钱)",
              r"账期(?:延|延长|延到|改|改成|放宽|放到)[^，。?？]{0,12}(?:要花|花|成本|代价|多少钱)")
STATUS = _re(r"\bstatus\b", r"\b(?:cash|liquidity|financial|funding|overall|current|our|my)\s+position\b", r"\bhow are we\b", r"\bhow'?s (?:our |the )?cash\b", r"\bheadroom\b",
             r"\bdashboard\b", r"\boverview\b", r"\bcash balance\b", r"\bwhere do we stand\b", r"现状", r"状况", r"状态",
             # 余额 and 情况怎么样 only with a cash or company subject: "本季度增值税情况怎么样", "按账户列一下余额" and
             # "竞争对手情况怎么样" ask about what the books do not hold (app/nl/ask.py answers them)
             r"现金(?:余额|情况)", r"(?:现金|银行|账上|账面|账户)余额", r"余额(?:是多少|多少|还有多少|还剩)", r"概况",
             r"^\s*(?:现在|目前|今天)?(?:的)?(?:情况|状况)怎么样",
             r"(?:现金|资金|财务|公司|我们|咱们|整体|总体|目前|现在)(?:的)?(?:情况|状况)怎么样",
             # "how much cash do we have", not "how much money has FLOW moved" (the activity log) or "how much money do we
             # need" (the funding need)
             r"\bhow much (?:cash|money)\s+(?:do|does|have|has|is|are|will|would)\s+(?:we|i|there|our|the company|the business)\b"
             r"(?!.{0,20}\b(?:need|raise|borrow|moved?|spent|spend)\b)",
             r"\bhow much (?:cash|money)\s+(?:is |are )?(?:left|in the bank|on hand|available)\b", r"\bhow much (?:cash|money)\s*\??\s*$",
             r"\bcash (?:on hand|do we have|position)\b", r"\bbank balance\b",
             r"\bcovenants?\b.{0,30}\b(?:look|looking|status|headroom|ok|okay|safe|risk)\b",
             r"账上", r"多少现金", r"(?:现金|资金|手上|手头|银行(?:里|上)?|户头)[^，。?？]{0,6}多少钱",
             r"^\s*(?:我们|咱们|公司)?(?:现在|今天|目前)?(?:还)?有多少钱", r"还有多少", r"(?:契约|财务指标).{0,10}(?:怎么样|情况|风险)",
             # forecasts and receivables: "show me the 13 week forecast", "list the open receivables", 现金流预测
             # ("cash flow" alone is a topic, not a request to see it: "a poem about cash flow" is not a status)
             r"\bforecast\b", r"\b\d{1,2}[- ]?week (?:forecast|projection|view|outlook)\b", r"\bprojection\b",
             r"\bcash ?flows? (?:forecast|projection|statement|position|situation|outlook|report)\b",
             r"\b(?:show|pull up|see|view|list|display|check)\b.{0,20}\bcash ?flows?\b",
             r"\b(?:how(?:'s| is| does)|what(?:'s| is| does))\b.{0,20}\bcash ?flows?\b.{0,15}(?:look|looking)?",
             r"\b(?:list|show|pull up|see|view|display|check)\b.{0,20}\b(?:receivables?|open invoices)\b",
             r"\b(?:open|outstanding) receivables\b", r"\baging\b", r"\bageing\b", r"\bwho owes us\b",
             r"现金流(?:预测|情况|怎么样|表|状况)", r"(?:现金流|资金|回款)?预测", r"应收(?:账款)?", r"未(?:收|回)(?:款|回)",
             r"谁欠(?:我们)?钱", r"账龄",
             # "pull up the ledger", "show me the books", "how much headroom is left on the credit line", 授信还剩多少额度
             r"\b(?:pull up|bring up|show|open|see|view|display|check|get)\b.{0,20}\b(?:ledger|books|accounts|balances?|numbers|figures)\b",
             r"\bhow much\b.{0,30}\b(?:left|available|unused|undrawn|remaining)\b.{0,30}\b(?:line|facility|facilities|credit)\b",
             r"\b(?:available|remaining|unused|undrawn)\s+(?:credit|headroom|facility|line)\b",
             r"(?:授信|额度|信用额度|贷款额度)[^，。?？]{0,10}(?:还剩|剩下|剩|还有|可用|能用|余额|多少)",
             r"(?:还剩|剩下|可用|能用)[^，。?？]{0,6}(?:额度|授信)")
# "any alerts?", "what needs me today", 有什么提醒: the owner asks what needs them (SHOW_ALERTS, checked before the
# status questions). It only reads the alerts; the cure runs on a later, direct "go ahead".
ALERTS = _re(r"\balerts?\b", r"\bnotifications?\b", r"\bwhat needs (?:me|my attention|attention|doing|action)\b",
             r"\b(?:anything|something) (?:needs?|requires?) (?:me|my attention|attention|action)\b",
             r"\banything (?:i|we) (?:should|need to|ought to|must|have to) (?:know|see|look at|handle|deal with|worry)\b",
             r"\bwhat should i (?:know|look at|deal with|handle)\b", r"\bany(?:thing)? (?:news|warnings?)\b",
             r"提醒", r"预警", r"告警", r"需要我(?:处理|关注|注意|看|决定)", r"有什么(?:需要|要)我", r"有什么(?:要紧|新情况|新消息)")
# Capabilities that are built but were not reachable from chat (tracker rows E1, E2). Each names its subject; the
# phrasings that already mean SHOW_STATUS ("how are we doing", "are we close to breaching a covenant?") keep doing so.
COMPARE_FINANCING = _re(
    r"\bcompare\b.{0,30}\b(?:financing|funding|loans?|sources?|options?|facilit\w*)\b",
    r"\b(?:financing|funding|loan|credit) options?\b",
    r"\b(?:cheapest|best|lowest[- ]cost|least expensive|most affordable)\b.{0,25}\b(?:financing|funding|loans?|sources?|facilit\w*|options?)\b",
    r"\b(?:financing|funding|loans?|sources?|facilit\w*|options?)\b.{0,25}\b(?:cheapest|cheaper|lowest cost|least expensive)\b",
    r"\bwhich (?:financing|funding|loan|source|facility)\b", r"\bwhat does each (?:source|option|facility|financing|loan)\b.{0,15}\bcost",
    r"哪种(?:融资|贷款|资金)", r"哪个(?:融资|贷款)", r"比较.{0,6}(?:融资|贷款|资金|方案)", r"融资(?:方案|选择|选项)",
    r"(?:各|每).{0,3}(?:融资|来源|渠道).{0,6}(?:成本|多少钱|利率)")
RECONCILE = _re(
    r"\breconcil\w*", r"\bdid\b.{0,40}\b(?:pay|paid)\b(?!.{0,30}\b(?:early|sooner|earlier|faster)\b)",
    r"\b(?:which|what|any)\b.{0,20}\b(?:receipts?|payments?)\b.{0,25}\b(?:missing|outstanding|late|overdue|not (?:in|arrived|received|come))",
    r"\bmissing (?:receipts?|payments?)\b", r"对账", r"核对.{0,6}(?:回款|收款|款项|账)",
    r"哪些.{0,4}(?:回款|收款|款).{0,6}(?:没到|未到|缺)")
RATIOS = _re(
    r"\bdscr\b", r"\bdebt[- ]service[- ]coverage\b", r"\bleverage\b", r"\bcovenant headroom\b",
    r"\bheadroom\b.{0,25}\bcovenants?\b",
    r"\b(?:inside|within|meeting|meet|satisfy|satisfying|comply|complying|compliant|compliance)\b.{0,25}\bcovenants?\b",
    r"\bcovenants?\b.{0,20}\b(?:ratios?|compliance|tests?)\b", r"偿债覆盖", r"杠杆", r"契约")
# Where a buyer's deal stands (brief 03): "where are we with Foshan?", "what did we sign with Foshan", 跟佛山的合同进展
DEAL = _re(
    r"\bwhere (?:are|do) we (?:stand )?with\b", r"\bwhat'?s (?:the|our) (?:deal|position|status) with\b",
    r"\b(?:our|the) (?:deal|contract|agreement|supply agreement) with\b", r"\b(?:contract|agreement)s? (?:with|for)\b",
    r"\bwhat did we (?:sign|agree)\b", r"\b(?:deal|contract) (?:status|summary|terms)\b",
    r"\b(?:remind me (?:of|about)|show me|summari[sz]e) (?:the |our )?(?:deal|contract|agreement)\b",
    r"\bterms (?:of|in) (?:the|our) (?:contract|agreement)\b",
    r"(?:跟|和|与)[^，。,.?？]{1,10}?的?(?:合同|协议|交易|生意|合作)", r"合同(?:进展|条款|情况|内容)", r"签了什么", r"我们签的")
CAPEX_ASK = _re(
    r"\b(?:buy|buying|purchase|purchasing|afford|invest(?:ing)? in|worth)\b.{0,40}\b(?:machine|machinery|equipment)\b",
    r"\b(?:machine|machinery|equipment|capex)\b.{0,40}\b(?:purchase|worth|afford|affordable|payback|npv)\b",
    r"\b(?:evaluate|assess|appraise|review)\b.{0,20}\b(?:machine|machinery|equipment|capex)\b", r"\bcapex\b",
    # "does the investment pay off?" asks whether the machine is worth it, not to repay a loan
    r"\b(?:investment|machine|machinery|equipment|purchase)\b.{0,20}\bpay (?:off|back|for itself)\b",
    r"买.{0,6}(?:设备|机器)", r"(?:设备|机器).{0,8}(?:划算|值得|购置|采购|买)", r"购置.{0,4}(?:设备|机器)",
    r"投资.{0,6}(?:划算|值得|回本|值不值)")
# The owner states a fact the agent cannot book from chat: "we have a supplier bill of ¥80,000 due on day 30, add it to
# the forecast", "record a ¥50,000 payable", "we will pay the supplier 10 days late", "EBITDA is actually ¥120,000",
# 记一笔, 新增账单, 延迟付款. RECORD_FACT only says so; it reads and writes nothing (checked after the requests the agent
# can act on: early payment, negotiation, repayment, funding).
RECORD_FACT = _re(
    r"\b(?:add|record|log|enter|book|register|insert|key in|note down)\b.{0,40}\b(?:bill|invoice|payable|expense|payment|outgoing)s?\b",
    r"\b(?:add|record|log|enter|book|register|insert)\b.{0,30}\b(?:to|into|in|on) (?:the |our )?(?:forecast|books|ledger|projection|cash ?flow|plan)\b",
    r"\b(?:we|i)\s+(?:have|got|owe|just got|received|will owe|need to pay|must pay)\s+(?:an?|the|another|new|our)?\s*(?:\w+\s+){0,2}"
    r"(?:bill|invoice|payable)s?\b",
    r"\bnew (?:supplier |vendor )?(?:bill|invoice|payable|expense)\b",
    r"\b(?:we|i)(?:'ll|\s+will|\s+are going to|\s+plan to|\s+might|\s+may|\s+must|\s+have to|\s+need to)?\s*"
    r"pay(?:ing)?\b.{0,40}\b(?:late|later|behind|delayed?|overdue)\b",
    r"\b(?:delay|postpone|defer|push back)(?:ing|ed)?\b.{0,25}\b(?:payment|paying|bill|payable|supplier)s?\b",
    r"\blate payment\b", r"\bpay(?:ing)? (?:the )?(?:supplier|vendor|landlord)s?\b.{0,20}\b(?:late|later|days late)\b",
    r"\bebitda\b.{0,30}\b(?:is|was|will be|has (?:been|changed)|now|actually|should be)\b.{0,30}\d",
    r"\b(?:update|change|set|correct|fix)\b.{0,20}\bebitda\b",
    r"记(?:一|下)?笔", r"记(?:一下|下来)?(?:这笔|账)", r"新增.{0,8}(?:账单|发票|应付|支出|费用|付款|款项|欠款)",
    r"(?:添加|录入|登记).{0,8}(?:账单|发票|应付|支出|费用|付款|款项)", r"(?:加|添加|计)(?:入|到|进)?.{0,6}(?:预测|预算|账上)",
    r"(?:延迟|推迟|延后|拖延)(?:付款|支付|还款|货款)", r"(?:晚|迟)(?:点|些)?(?:付|支付)", r"(?:拖欠|晚付|迟付)",
    r"(?:有|收到|来了|多了)(?:一|1)?[张笔份](?:\S{0,8})?(?:账单|发票|应付)",
    r"(?:供应商|供货商).{0,6}(?:账单|发票|货款)", r"(?:ebitda|EBITDA).{0,10}(?:是|为|变成|调整|改成|更新|其实).{0,10}\d")
BORROWER_FILE = _re(
    r"\b(?:borrower|lender|loan|bank)[’']?s?\s+(?:file|pack|package|dossier)\b", r"\bloan application (?:file|pack|package)\b",
    r"借款人(?:资料|文件|材料)", r"(?:贷款|申贷|授信)(?:申请)?(?:资料|材料|文件)", r"贷款包")
# A question about the position ("are we close to breaching a covenant?", "会不会跌破储备线？"): it asks, so
# it is SHOW_STATUS even when it names the reserve or a shortfall (checked before FUND).
STATUS_QUESTION = _re(
    r"^\s*(?:are|is|will|would|could|do|does|am)\s+(?:we|there|it|our|the)\b.{0,60}"
    r"\b(?:breach\w*|break\w*|below|under|short|enough|dip\w*|fall\w*|drop\w*|covenants?|reserve|floor|minimum|gap)\b",
    r"\b(?:any|close to|near|at risk of)\s+(?:a\s+|any\s+)?(?:covenant|breach)",
    r"会不会.{0,12}(?:跌破|低于|违反|突破|违约|缺钱|不够)", r"(?:有没有|是否).{0,10}(?:违约|违反|跌破|缺口)",
    # "Am I safe this month?", "Are we OK for cash?", "Are we covered until payday?": asks about the owner's own position
    # (not a deal: "are we OK to accept this offer?" names an offer, an invoice or a buyer and stays out)
    r"^(?!.*\b(?:offers?|deals?|accept\w*|buyers?|invoices?|approv\w*|contracts?|quotes?|terms)\b)\s*"
    r"(?:am|are|is|will|would|can|could)\s+(?:i|we|our|my)\b.{0,40}\b(?:safe|ok|okay|fine|covered|comfortable|alright)\b",
    r"\bcash runway\b", r"\brunway\b", r"\bhow is (?:our|the|my) cash\b",
    r"\bhow long (?:will|does|can|would) (?:our |the |my )?(?:cash|money|runway)\b",
    r"\b(?:will|do|would) (?:we|i) have enough (?:cash|money)\b",
    r"^\s*(?:我们?|咱们?|公司|本公司)[^，。？?！!]{0,8}安全吗", r"(?:现金|资金|钱)(?:够不够|够吗|够用吗|充足吗|紧张吗|安全吗|还够)",
    # what can be spent against the reserve: "How much can I spend today without breaking the reserve?", 今天我最多能花多少钱
    r"\bhow much (?:can|could) (?:i|we) (?:spend|use|take out)\b", r"(?:能|可以)(?:动用|用|花)多少(?:钱|现金)?",
    r"(?:够不够|够)(?:用的?)?(?:现金|资金|钱)", r"现金跑道", r"(?:现金|资金|钱).{0,6}(?:能|可以)?撑(?:多久|多长时间|几天)",
    r"现金(?:怎么样|如何|还好吗|还行吗)")
REPAY = _re(r"\brepay", r"\bpay (?:back|down|off)\b", r"\bpay (?:the |our )?(?:credit |bank )?line (?:back|down|off)\b",
            r"\bclear (?:the |our )?(?:balance on the |outstanding balance on the |outstanding )?(?:credit |bank )?line\b",
            r"\bsettle (?:the |our )?(?:credit |bank )?line\b", r"还款", r"偿还", r"还清", r"归还",
            r"(?:授信|信用|银行|额度).{0,8}还(?:掉|了|上|回去)", r"把.{0,12}还(?:掉|了|上|回去)")
FUND = _re(r"\bfund (?:the |it\b|this\b|that\b|our )", r"\bfund it\b", r"\bcover (?:the |our )?(?:cash )?(?:gap|shortfall)",
           r"\bclose (?:the )?gap\b", r"\bfunding gap\b", r"\bcash gap\b", r"\bshortfall\b", r"\bbridge (?:the )?gap\b",
           r"\bdraw\b", r"补(?:足|上)?(?:资金)?缺口", r"资金缺口", r"填补", r"提款", r"支取", r"动用.{0,6}额度",
           r"\bcover (?:the |our |this |that )?\w+ (?:gap|shortfall)\b",
           r"缺口(?:给)?补(?:上|足|齐|平)", r"补(?:上|足|齐|平)?.{0,6}缺口",
           # "从授信额度里提10万出来", "在额度上借20万"
           r"(?:额度|授信|信用额度|贷款额度)(?:里|中|上)?.{0,4}(?:提|借|拿|取|支)(?:款|现|用|出)?.{0,3}(?:\d|[一二两三四五六七八九十])",
           r"(?:提|借|拿|取)(?:款|现)?\s*(?:\d[\d,.]*|[一二两三四五六七八九十]+)\s*(?:万|千|元|块).{0,6}(?:出来|用|周转)")
# A request to look for options rather than to act ("find me the cheapest way to cover the gap",
# 帮我找最便宜的方式补上): FUND_GAP proposes the plan and waits for "go ahead", in either language.
FUND_EXPLORE = _re(
    r"\b(?:find|look for|figure out|work out|suggest|recommend|propose|show me|what(?:'s| is| are)|which is)\b.{0,40}"
    r"\b(?:way|ways|option|options|cheapest|best|plan|route)\b",
    r"\bhow (?:can|could|should|do|would) we\b", r"\bany (?:way|option)s?\b",
    r"(?:找|想|看看|推荐|建议|有没有|有什么|怎么|如何|哪种|哪个).{0,12}(?:办法|方式|方法|方案|途径|最便宜|最划算|最省)",
    r"怎么补|如何补|怎么解决|如何解决")
# Needs described, not the funding asked for ("payroll is due and we are short", 工资不够): FUND_GAP, but the plan is
# proposed and waits for "go ahead" instead of executing on a reading this loose.
FUND_SOFT = _re(
           r"\b(?:payroll|wages|salaries|rent|suppliers?|bills)\b.{0,50}\b(?:short|can'?t cover|cannot cover|not enough|tight|cover (?:it|them))\b",
           r"\bcover (?:the )?(?:payroll|wages|salaries|rent|bills)\b", r"\b(?:we'?re|we are|running)\s+(?:a bit\s+)?(?:short|low|tight)\b",
           r"\bshort (?:of|on) (?:cash|money|funds)\b", r"\btop (?:up|off) (?:the )?(?:cash|account|balance|bank)\b",
           r"\b(?:don'?t|doesn'?t|do not|never|won'?t)\s+(?:let\s+(?:cash|us|the balance)\s+)?(?:dip|fall|drop|go)\w*\s+(?:below|under)\b",
           r"\bstay (?:above|over) (?:the )?(?:reserve|floor|minimum)\b", r"\baccount is (?:thin|low|tight)\b",
           r"(?:工资|薪水|房租|货款|账单).{0,12}(?:不够|缺|付不起|发不出)", r"(?:钱|资金|现金)不够", r"缺钱", r"安排(?:一下)?融资",
           r"找(?:点)?钱", r"借(?:点)?钱", r"周转", r"(?:别|不要|不能)(?:让)?.{0,6}(?:跌破|低于)(?:储备|底线|最低)")
ACCELERATE = _re(r"\b(?:get|be|getting) paid (?:early|sooner|faster)\b", r"\b(?:get|have)\b.{0,40}\bpaid (?:early|sooner|faster)\b",
                 r"\bcollect\b.{0,50}\b(?:sooner|earlier|early|faster|quicker)\b", r"\bearly[- ]pay\b",
                 r"\b(?:pay|paid|settle|settled|clear|cleared)\b(?!.{0,50}\b(?:line|loan|facility|debt|bank|back|off)\b)"
                 r".{0,40}\b(?:sooner|earlier|faster|quicker)\b",
                 r"\b(?:get|ask|make)\b.{0,30}\bto pay (?:early|sooner|earlier)\b",
                 r"早点(?:付|给钱|打款)", r"提前(?:付|打款|给钱)", r"早付", r"尽快(?:付|打款|收)",
                 r"\b(?:money|cash|payment|invoice)\b.{0,20}\bin (?:sooner|earlier|faster)\b", r"\bearly (?:payment|settlement)\b",
                 r"\bcollect (?:early|sooner)\b", r"\baccelerate\b", r"\bspeed up (?:the )?(?:payment|collection|receipt)",
                 r"提前(?:收款|回款|结算)", r"早点(?:收|回)款", r"加快回款", r"尽快收回",
                 r"\b(?:get|ask|make|have|persuade|convince|push|nudge)\b.{0,30}\bto\s+(?:pay|settle|clear|remit)\b.{0,40}"
                 r"\b(?:early|earlier|sooner|faster|ahead of time|before (?:the )?due)\b",
                 r"\b(?:get|bring|pull)\b.{0,30}\b(?:money|cash|payment|receivable|invoice|funds)\b.{0,15}\bin\s+(?:early|earlier|sooner|faster)\b",
                 r"\b(?:pull|bring|move)\b.{0,30}\b(?:receivable|invoice|payment|collection|money|cash)\b.{0,10}\bforward\b",
                 r"\b(?:pull|bring|move) forward\b.{0,30}\b(?:receivable|invoice|payment|collection)\b",
                 r"催.{0,8}(?:回款|付款|打款|结款)")
NEGOTIATE = _re(r"\bnegotiat", r"\bsend (?:the |our |both )?counters?\b", r"\bcounter[- ]?offer", r"\bhaggle\b",
                r"\bpush\s+back\b", r"\bgo\s+back\s+to\s+(?:them|him|her|the buyer|\w+)\s+with\b", r"\bcome\s+back\s+(?:to\s+\w+\s+)?with\b",
                r"\b(?:offer|propose|suggest)\s+(?:them\s+)?(?:something\s+)?(?:smaller|lower|less)\b", r"回绝.{0,10}(?:再|重新)",
                r"\bbargain\b", r"谈判", r"还价", r"议价", r"反报价", r"发(?:送)?反要约",
                r"^\s*counter\b", r"\bcounter (?:them|him|her|the buyer|it|at|with)\b",
                r"谈一下", r"谈谈", r"去谈", r"跟.{1,10}谈", r"砍价")
# An explicit negotiating verb outranks an early-payment cue: "跟佛山谈一下，提前付款最多给0.7%" negotiates.
NEGOTIATE_VERB = _re(r"\bnegotiat", r"^\s*counter\b", r"\bcounter (?:them|him|her|the buyer|it|at|with)\b", r"\bpush\s+back\b",
                     r"谈判", r"谈一下", r"谈谈", r"去谈", r"跟.{1,10}谈", r"还价", r"议价", r"砍价")
EVALUATE = _re(r"\bevaluate\b", r"\bassess\b", r"\bcheck (?:this|the|that|offer)\b", r"\breview (?:this|the|that)\b",
               r"\banaly[sz]e\b", r"\bis (?:this|it) (?:a )?good\b", r"\bshould (?:we|i) accept\b", r"\bbuyer (?:says|wrote|sent)\b",
               r"评估", r"审核", r"分析", r"看看这", r"要不要接受", r"能不能接受", r"买家说")
# "should we take it", "good deal or not?", 能接吗: the owner asks for a verdict on an offer, not for our own plan
EVAL_QUESTION = _re(r"\bshould (?:we|i) (?:take|accept|agree to|go (?:for|with)|say yes)\b", r"\bgood deal\b", r"\bworth it\b",
                    r"\bis (?:this|it|that) (?:ok|okay|acceptable|fine|good|a good deal|worth it)\b", r"\bcan we (?:accept|take|agree to|live with)\b",
                    r"\b(?:do we|should we) (?:take|accept)\b", r"\bthoughts\??\s*$", r"\bwhat do you think\b", r"\bdeal or not\b",
                    r"能接吗", r"能不能接", r"可以接吗", r"能答应吗", r"要不要接", r"能接受吗", r"可以接受吗", r"划算吗", r"值不值", r"这个能接",
                    r"行不行", r"怎么看")
# "Foshan says they'll pay early at 1.2% if we go to 60 days", 东莞那边说下季度要我们返1个点: a reported offer
REPORTED_OFFER = rx(
    r"(?:\b(?:buyer|customer|client|they|he|she)|(?-i:[A-Z][A-Za-z&]+)(?:['’]s)?(?:\s+[A-Za-z&]+){0,3}?)\s+"
    r"(?:just\s+)?(?:says?|said|offers?|offered|is offering|wants?|proposes?|proposed|is proposing|asks? for|asked for|came back with)\s+"
    r"(?:that\s+)?(?P<en>.{8,}?)(?=\s*(?:[.?!。？！]\s*(?:[A-Z]|$)|$|[.?!]?\s*(?:should|good deal|is (?:this|it|that)|can we|what do|thoughts|worth)))"
    r"|(?:[一-鿿]{2,6}?)(?:那边|这边|客户|买家)?(?:刚才?|刚刚)?(?:说|发来的?|来信说?|提出|要求|回复说?)\s*[:：,，]?\s*(?P<zh>[^？?]{4,}?)"
    r"(?=[，,。\s]*(?:这个|那|这)?(?:能接|能不能接|可以接|能答应|要不要接|能接受|可以接受|划算|值不值|行不行|怎么看))", re.IGNORECASE)
ZERO_FORWARD_EXTRA = _re(r"\bno\s+(?:forward\s+)?(?:rebates?|concessions?|give-?aways?)\b", r"不要?(?:答应|同意|给)(?:任何)?(?:返点|返利|让步|让利|优惠)",
                         r"别(?:答应|同意)(?:任何)?(?:返点|返利|让步|让利)")
AMBIGUOUS = _re(r"\b(?:help|sort out|do something about|handle|deal with|fix)\b.{0,30}\b(?:cash|money|finances?|liquidity)\b",
                r"处理一下(?:资金|现金|钱)", r"帮我(?:管|弄|搞)一下(?:钱|资金)", r"资金怎么办", r"钱的问题",
                # vague delegation with no task named: one clarifying question, not the capability list (EV-09)
                r"^\s*(?:can|could|would|will) you\s+(?:please\s+|just\s+)?(?:handle|sort|deal with|take care of|fix|manage|look after|do)"
                r"\s+(?:it|this|that|things|everything|something)\s*(?:for me\s*)?(?:please\s*)?[.!?？]*\s*$",
                r"^\s*(?:please\s+|just\s+)?(?:handle|sort|sort out|deal with|take care of|fix|manage)\s+(?:it|this|that|things|everything)\b",
                r"\b(?:do|does) (?:the |what(?:ever)? (?:is|'s) )?(?:usual|normal|same as (?:always|usual|before))\b",
                r"\bthe (?:usual|normal thing|normal stuff)\b", r"\byou decide\b", r"\byour call\b", r"\bup to you\b",
                r"\bwhatever you think\b", r"看着办", r"你(?:来)?决定", r"你看着", r"帮我处理", r"处理一下", r"帮我搞定", r"^\s*搞定",
                r"老样子", r"照旧", r"老规矩", r"你来定", r"你定吧",
                # a task named only by a pointer: "do the thing with Foshan", "make it cheaper", 那个单子怎么说
                r"\bdo the (?:thing|needful|stuff)\b", r"\bmake (?:it|this|that) (?:cheaper|better|work|happen|right)\b",
                r"\b(?:sort|figure) (?:it|this|that) out\b", r"那个(?:单子|事情?|东西)", r"那件事", r"那笔(?:单|生意)?怎么",
                # a task named only by a pointer: "handle the bank thing", "deal with the thing from yesterday"
                r"\b(?:handle|sort(?: out)?|deal with|take care of|look into|fix|do|check on)\s+(?:the|that|this)\s+(?:[\w-]+\s+){0,2}?(?:thing|stuff|issue|matter|situation|business)\b",
                r"\bthe\s+thing\s+(?:from|with|about|we|you|i)\b",
                r"^\s*(?:is|was|are)\s+(?:it|that|this|they)\s+(?:ok(?:ay)?|fine|good|alright|done|sorted|ready)\s*[?？!.]*\s*$",
                r"^\s*(?:can|could)\s+we\s+(?:afford|do|manage)\s+(?:it|this|that)\s*[?？!.]*\s*$",
                r"^\s*(?:那个|这个|那件事|那事|那单|这单)\s*(?:怎么样了?|咋样了?|如何了?|呢|行吗|可以吗|弄好了吗|搞定了吗|好了吗|怎么说)\s*[?？!！。]*\s*$",
                r"^\s*(?:what about|how about|and)\s+(?:it|that|this|them)\s*[?？]*\s*$")
CAPEX = _re(r"\bmachine\b", r"\bequipment\b", r"\bcapex\b", r"设备", r"机器", r"购置")
ZERO_FORWARD = _re(r"without giving (?:anything|something) away", r"\bnothing away\b", r"\bno (?:forward )?concessions?\b",
                   r"\b(?:don'?t|do not|never|without)\s+giv(?:e|ing)\s+(?:\w+\s+){0,2}?away\b",
                   r"\bnothing (?:in return|forward|else)\b", r"不要?(?:给|做)(?:任何)?(?:让步|让利|优惠)", r"别(?:给|让)(?:任何)?(?:让步|让利|优惠)",
                   r"\bzero (?:forward )?concessions?\b", r"不(?:做|给)(?:任何)?让步", r"不让利", r"不给任何(?:优惠|让利)")
REBATE_WORD = _re(r"\brebates?\b", r"\bback\b", r"\bcashback\b", r"返利", r"返点", r"返现", r"返")
USE_FINANCING = _re(r"invoice financing", r"\bfactoring\b", r"\bfinance the invoice\b", r"发票融资", r"保理")
HARDLINE = _re(r"\bhard[- ]?line\b", r"\btough\b", r"\bwalks?\b", r"\brefuses?\b", r"强硬")
APPROVAL_REF = _re(r"\bapproval\b", r"\bpending\b", r"\bqueue", r"审批", r"待批")

TIER3: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SIGN_PERSONAL_GUARANTEE", _re(r"personal(?:ly)? guarant", r"\bguarantor\b", r"个人担保", r"个人连带", r"连带担保")),
    ("PLEDGE_COLLATERAL", _re(r"\bpledge\b", r"\bcollateral\b", r"\bmortgage\b", r"抵押", r"质押")),
    ("ISSUE_EQUITY", _re(r"\bissue (?:new )?(?:equity|shares)\b", r"\bsell (?:a )?stake\b", r"\bequity\b", r"股权", r"增发",
                         r"出让股份")),
    ("CHANGE_MANDATE", _re(r"\b(?:change|raise|lower|increase|decrease|edit|modify|update|override|bypass|ignore)\b.{0,20}"
                           r"\b(?:mandate|floor|reserve|cap|limits?)\b",
                           r"修改.{0,4}(?:授权|限额|底线|上限)", r"(?:降低|取消|提高).{0,6}(?:储备|底线|上限|限额)")),
)

FIXTURE_RE = rx(r"\b(EX\s?\d{2}[A-Z]?|SEC[_ ]DEMO)(?:_[A-Z0-9_]+)?\b", re.IGNORECASE)
QUOTED_RE = re.compile(r"[\"“「『](.{8,}?)[\"”」』]|(?<![A-Za-z])['‘](.{8,}?)['’](?![A-Za-z])", re.DOTALL)
BUYER_SAYS_RE = rx(
    r"(?:buyer (?:says|wrote|sent)|message)\s*[:：]\s*(.{8,})$|买家说\s*[:：]\s*(.{4,})$"
    # "Foshan just sent this: 'We'll pay …'", "the customer wrote:", 东莞那边发来：, 佛山客户说：
    r"|\b(?:buyer|customer|client|they|he|she|[a-z][a-z]+(?: [a-z][a-z&]+){0,3})\s+(?:just\s+)?(?:says|said|wrote|sent(?: (?:this|us|me|over))?"
    r"|messaged|emailed|texted|replied|offered|proposed)\s*[:：]\s*(.{8,})$"
    r"|(?:客户|买家|买方|对方|那边|他们)(?:刚才?|刚刚)?(?:说|发来|来信|回复|提出|发消息说|发了)(?:了)?\s*[:：]\s*(.{4,})$"
    r"|[一-鿿]{2,6}?(?:那边|客户)?(?:刚才?|刚刚)?(?:发来的?|来信|回复|发消息)(?:了|说)?\s*[:：]\s*(.{4,})$",
    re.IGNORECASE | re.DOTALL)
# The owner's own question after a pasted offer: dropped before the offer is compiled.
OWNER_TAIL = _re(r"\bwhat do you think\b", r"\bthoughts\b", r"\bshould (?:we|i) (?:accept|take|agree)",
                 r"\bcan we (?:accept|take|agree|do)\b", r"\bis (?:this|it|that) (?:ok|okay|good|acceptable|fine)\b",
                 r"帮我看看", r"能不能接", r"能接吗", r"能答应吗", r"可以接受吗", r"能接受吗", r"怎么看", r"要不要接",
                 r"行不行", r"可以吗")
APPROVAL_ID_RE = rx(r"\bAPR-\d{6}\b", re.IGNORECASE)

ORDINALS = {"1": 1, "one": 1, "first": 1, "1st": 1, "第一": 1, "一": 1,
            "2": 2, "two": 2, "second": 2, "2nd": 2, "第二": 2, "二": 2,
            "3": 3, "three": 3, "third": 3, "3rd": 3, "第三": 3, "三": 3,
            "both": 99, "all": 99, "全部": 99, "都": 99, "两个都": 99}

# ---------------------------------------------------------------- values

_MONEY_RE = rx(
    r"(?P<pre>¥|￥|rmb\s*|cny\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>million|k\b|千|万|元|yuan\b|块)?",
    re.IGNORECASE)
_RATE_RE = rx(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|percent\b|bps?\b|个基点)", re.IGNORECASE)
_DAYS_RE = rx(r"(?P<num>\d{1,3})\s*(?:-\s*)?(?:days?\b|天|日)", re.IGNORECASE)
_INVOICES_RE = rx(r"(?:next|following)\s+(?P<n>\d+|two|three|four|five|six)\s+invoices|(?:接下来|后续)(?P<zh>\d+)张",
                          re.IGNORECASE)
_WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_UNIT = {"k": 1_000, "千": 1_000, "万": 10_000, "million": 1_000_000}


@dataclass(frozen=True)
class Found:
    value: int
    start: int
    end: int


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def amounts(text: str) -> list[Found]:
    """Money amounts with a currency marker or a unit (¥420k, 50万元, 500,000 yuan) as integer fen."""
    t = unicodedata.normalize("NFKC", text)
    out: list[Found] = []
    for m in _MONEY_RE.finditer(t):
        pre, unit = m.group("pre"), (m.group("unit") or "").lower()
        if not pre and not unit:
            continue
        tail = t[m.end():m.end() + 2]
        if tail.strip().startswith("%"):
            continue
        d = _dec(m.group("num"))
        if d is None:
            continue
        fen = d * _UNIT.get(unit, 1) * 100
        if fen != fen.to_integral_value() or fen <= 0:
            continue
        out.append(Found(int(fen), m.start(), m.end()))
    return out


def rates(text: str) -> list[Found]:
    """Rates as integer bp: 0.85% -> 85, 80bp -> 80."""
    t = unicodedata.normalize("NFKC", text)
    out: list[Found] = []
    for m in _RATE_RE.finditer(t):
        d = _dec(m.group("num"))
        if d is None:
            continue
        unit = m.group("unit").lower()
        bp = d * 100 if unit in ("%", "percent") else d
        if bp != bp.to_integral_value() or bp < 0 or bp > 10_000:
            continue
        out.append(Found(int(bp), m.start(), m.end()))
    # 千分之六, 1个点, 99.3折, "half a percent": the compiler's own rate grammar
    for f in find_rates(t):
        if 0 <= f.value <= 10_000 and not any(f.start < o.end and o.start < f.end for o in out):
            out.append(Found(f.value, f.start, f.end))
    return sorted(out, key=lambda x: x.start)


def days(text: str) -> list[Found]:
    t = unicodedata.normalize("NFKC", text)
    return [Found(int(m.group("num")), m.start(), m.end()) for m in _DAYS_RE.finditer(t) if 0 < int(m.group("num")) <= 365]


def invoices(text: str) -> int | None:
    m = _INVOICES_RE.search(unicodedata.normalize("NFKC", text))
    if not m:
        return None
    raw = m.group("n") or m.group("zh")
    return int(raw) if raw.isdigit() else _WORD_NUM.get(raw.lower())


def ordinal(text: str) -> int | None:
    t = norm(text).strip(" .!?。！？")
    for word, n in sorted(ORDINALS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", t) if word.isascii() else word in t:
            return n
    return None


# ---------------------------------------------------------------- names

_ZH_ALIASES = {"foshan": ("佛山",), "dongguan": ("东莞",)}


def counterparty_aliases(state: FinancialState) -> dict[str, tuple[str, ...]]:
    """Registry id -> lower-case aliases: the id, the full name, its first word and a zh city name."""
    out: dict[str, tuple[str, ...]] = {}
    for cp in state.counterparties:
        if cp.role not in ("BUYER", "LENDER"):
            continue
        first = cp.name.split()[0].lower().strip(".,")
        names = [cp.id.lower(), cp.id.lower().replace("-", " "), cp.name.lower(), first]
        names += list(_ZH_ALIASES.get(first, ()))
        out[cp.id] = tuple(dict.fromkeys(n for n in names if len(n) >= 2))
    return out


def find_counterparty(text: str, state: FinancialState, role: str | None = "BUYER") -> list[str]:
    t = norm(text)
    roles = {c.id: c.role for c in state.counterparties}
    hits = []
    for cp_id, names in counterparty_aliases(state).items():
        if role and roles.get(cp_id) != role:
            continue
        if any((re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", t) if n.isascii() else n in t) for n in names):
            hits.append(cp_id)
    return hits


FACILITY_WORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CREDIT_LINE", _re(r"\bcredit line\b", r"\bthe line\b", r"\bline\b", r"\brevolver\b", r"授信", r"信用额度", r"额度")),
    ("INVOICE_FINANCING", _re(r"invoice financing", r"\bfactoring\b", r"发票融资", r"保理")),
)


# ---- the questions the Business pages suggest (app/nl/reads.py answers them; rules.py and the handlers share these) ------
CHANGES_ASK = _re(
    r"\bwhat(?:['’]s| is| has| have)?\s+(?:has\s+|have\s+)?(?:changed|new|different|happened)\b",
    r"\bwhat\s+changed\b", r"\banything\s+(?:new|changed|different)\b", r"\bwhat\s+did\s+i\s+miss\b",
    r"\bsince\s+(?:my|the)\s+last\s+(?:visit|login|time)\b", r"\bcatch\s+me\s+up\b",
    r"有什么变化", r"发生了什么", r"什么变化", r"变化了什么", r"有什么新(?:变化|动态)", r"自上次", r"上次之后")
WAITING_ASK = _re(
    r"\bwhat\s+(?:are|is)\s+(?:we|you|i)\s+(?:still\s+)?waiting\s+(?:for|on)\b", r"\bwaiting\s+(?:for|on)\s+what\b",
    r"\bwhat(?:['’]s| is)\s+(?:still\s+)?(?:pending|outstanding|open)\b", r"\bwhat\s+are\s+we\s+waiting\b",
    r"在等什么", r"等什么", r"等待什么", r"还在等")
ARRIVAL_ASK = _re(
    r"\bwhen\s+(?:does|do|will|is)\b.{0,30}\b(?:money|cash|funds?|funding|payments?)\b.{0,20}\b(?:arrive|land|come|get here|in)\b",
    r"\bwhen\s+(?:will|do)\s+(?:we|i)\s+(?:get|receive)\b.{0,20}\b(?:money|cash|funds?|paid|payment)\b",
    r"\bwhen\s+(?:does|do|will|is)\s+the\s+(?:money|cash|funding)\b",
    r"什么时候(?:到账|收到|到)", r"何时(?:到账|收到)", r"资金.{0,6}什么时候", r"钱.{0,6}什么时候")
OVERDUE_ASK = _re(
    r"\bwhat(?:['’]s| is| are)\s+(?:overdue|late|past due)\b", r"\bwhat\s+is\s+overdue\b", r"\bwho\s+(?:is|are)\s+(?:late|overdue)\b",
    r"\bwho\s+(?:should|do)\s+(?:i|we)\s+(?:chase|call|follow up|remind|collect)\b", r"\bchase\s+first\b",
    r"\bwho\s+(?:has not|hasn'?t|haven'?t)\s+paid\b", r"\bwho\s+to\s+chase\b",
    r"\b(?:which|what|any)\b.{0,20}\b(?:invoices?|payments?|receipts?|receivables?)\b.{0,25}\b(?:late|overdue|past due)\b",
    r"逾期", r"先催", r"该催", r"催(?:收|款|哪)", r"谁(?:还)?没(?:有)?付",
    # "who is paying late?", 谁拖欠我们的款: who is late, not a payment delay of ours to record
    r"\bwho\s+(?:is|are)\s+paying\s+(?:us\s+)?late\b", r"谁(?:在)?(?:拖欠|晚付|迟付)", r"哪些?(?:客户|买家|买方).{0,4}(?:拖欠|晚付|迟付)")
OWED_ASK = _re(
    r"\bwho\s+(?:still\s+)?owes?\s+(?:us|me)\b", r"\bwho\s+(?:still\s+)?owes?\s+(?:the\s+)?(?:company|business)\b",
    r"\bhow\s+much\b.{0,25}\b(?:owed|do\s+(?:they|customers|buyers|our\s+customers)\s+owe)\b",
    r"\bwho\s+hasn'?t\s+paid\s+us\s+yet\b",
    r"谁欠(?:我们|我)?(?:的)?(?:多少)?钱", r"谁欠(?:我们|我)", r"(?:客户|买方|买家).{0,6}欠(?:我们)?(?:多少)?(?:钱|款)",
    r"欠(?:我们|我)(?:的)?(?:多少)?(?:钱|款)")
LATE_PAYMENT_ASK = _re(
    r"\b(?:late|delayed?|overdue|slips?|slipped|doesn'?t arrive|does not arrive|never arrives?)\b.{0,40}\b(?:payment|invoice|receipt|receivable)s?\b",
    r"\b(?:payment|invoice|receipt|receivable)s?\b.{0,40}\b(?:is|are|comes?|arrives?|gets?)\b.{0,6}\b(?:late|delayed|overdue)\b",
    r"\b(?:payment|invoice|receipt)s?\b.{0,30}\bdoesn'?t arrive\b", r"\bpays?\s+late\b",
    # "pays 30 days late", "the invoice slips a month", 晚30天付款, 款晚一个月到
    r"\bpays\b.{0,24}\blate\b", r"\b(?:they|customers?|buyers?|clients?)\s+pay\b.{0,24}\blate\b",
    r"\b(?:payment|invoice|receipt|receivable)s?\b.{0,20}\bslips?\b",
    r"(?<!我们)(?<!我)晚\s?(?:\d+|[一二两三四五六七八九十]+)\s?(?:个)?(?:天|日|周|星期|月)(?:才)?(?:付|到|回|收)",
    r"(?:款|付款|回款|收款|发票).{0,10}(?:延迟|晚到|晚付|逾期|没到|迟到|延误)", r"(?:延迟|晚到|晚付|逾期|迟到|延误).{0,10}(?:款|付款|回款|收款|发票)")
# "this payment", 这笔款项: the payment the page shows (its binding), not one the question names
THIS_PAYMENT = _re(r"\b(?:this|that)\s+(?:payment|invoice|receipt|one)\b", r"这笔", r"这张", r"该笔", r"那笔")
ACCEPT_ASK = _re(r"\baccept(?:ed|ing)?\b", r"\bagree(?:d)?\s+to\b", r"\btake\s+(?:the|their|this)\s+(?:deal|offer|terms)\b",
                    r"接受", r"答应", r"同意")
OPTION_ASK = _re(r"\boption\s+([a-d])\b", r"\bcounter\s+([a-d])\b", r"(?:方案|选项|还价)\s?([a-dA-D])\b", r"\b([a-d])\s?(?:方案|选项)")
PLAN_ASK = _re(r"\bplan\b", r"\bchoose\b", r"\bchose\b", r"\bchosen\b", r"\brecommend", r"\bcheapest\b", r"方案", r"计划", r"推荐")

READ_QUESTION = re.compile(r"^\s*(?:what|when|who|whom|which|how|where|why|is|are|do|does|did|can|could|will|would|should|show|tell)\b"
                            r"|[?？]\s*$|什么|谁|哪|吗|多少|几|怎么|如何", re.IGNORECASE)

# ---- questions about the books (ASK_BOOKS: app/nl/ask.py answers them; rules.py routes them) ---------------------------
#
# An information question: a wh-word, an inverted be/do/have auxiliary with a subject, a recommendation question ("should
# we ...?"), "any ...?", a trailing question mark, or a Chinese interrogative. A question never proposes a plan, compiles an
# offer, queues or executes anything, or writes a refused operation to the log: rules.py reads it before every action rule.
_ASK_SUBJECT = (r"(?:we|i|you|they|it|there|our|the|this|that|these|those|any|anyone|anybody|anything|someone|somebody|flow"
                r"|my|he|she)")
_ASK_START = (
    r"^\s*(?:(?:so|and|ok|okay|hey|hi|also|but|then|right|now|quick question|one question|question)[ ,:]+)*"
    r"(?:what|what['’]s|whats|which|who|who['’]s|whom|whose|when|when['’]s|where|where['’]s"
    r"|why(?!\s+(?:don['’]?t|not)\b)|how(?!\s+about\b)"
    r"|(?:is|isn['’]t|are|aren['’]t|was|were|does|doesn['’]t|do(?!\s+not\b)|did|didn['’]t|has|hasn['’]t|have|haven['’]t|had)"
    rf"\s+{_ASK_SUBJECT}\b"
    r"|(?:should|shall)\s+(?:we|i)\b|any(?:thing|one|body)?\b)")
_ASK_ZH_WORDS = r"什么|多少|哪|谁|是否|要不要|有没有|几(?:天|个|笔|次|号|月|周|时|年)|怎么|为什么|为何|如何"
ASK_EN = _re(_ASK_START, r"\?\s*$")
ASK_ZH = re.compile(_ASK_ZH_WORDS + r"|(?:吗|呢|么|嘛)\s*[?？。.!！~～]*\s*$|[?？]\s*$")
# The plain question forms only (a wh-word, an inverted auxiliary, a Chinese interrogative word), not a bare "?" or 吗:
# what an otherwise unread message needs before it goes to the answer layer.
ASK_WORD = _re(_ASK_START, _ASK_ZH_WORDS)
# A request phrased as a question ("can you draw ¥100k?", "could we get Foshan to pay early?", 能不能让他们早点打款, "FLOW能
# 替我签个人担保吗"): it keeps its action reading, which proposes at most (consent.py decides what runs, unchanged).
ASK_REQUEST = _re(r"\b(?:can|could|would|will|won['’]t)\s+(?:you|u|flow)\b(?!['’]s)", r"^\s*(?:can|could)\s+(?:we|i)\b",
                  r"[,，;]\s*(?:can|could)\s+(?:we|i)\b", r"\bplease\b", r"\bpls\b",
                  r"能不能", r"可不可以", r"能否", r"可否", r"帮我", r"帮忙", r"麻烦", r"^\s*请", r"你能", r"你可以", r"您能",
                  r"您可以", r"(?<!不)能[^，。？?]{0,20}(?:吗|么)", r"可以[^，。？?]{0,20}(?:吗|么)")
# A request addressed to FLOW ("could you repay the loan?", 你能把设备拿去抵押吗)
ASK_YOU = _re(r"\b(?:can|could|would|will|won['’]t)\s+(?:you|u|flow)\b(?!['’]s)", r"你能", r"你可以", r"您能", r"您可以", r"帮我",
              r"帮忙", r"麻烦", r"^\s*请", r"\bplease\b")
# An attempt asked about ("did anyone try to change our limits?", 有人试图修改我们的限额吗): answered from the log.
ASK_ATTEMPT = _re(r"\b(?:anyone|anybody|someone|somebody)\b", r"\b(?:tr(?:y|ied|ying)|attempt\w*)\b", r"有人", r"试图",
                  r"尝试", r"企图")


def is_question(text: str) -> bool:
    """Whether the owner's own words ask for information (ASK_EN / ASK_ZH) and are not a request phrased as one."""
    t = unicodedata.normalize("NFKC", text).strip()
    if not t or ASK_REQUEST.search(t):
        return False
    return bool(ASK_EN.search(t) or ASK_ZH.search(t))


def is_asking(text: str) -> bool:
    """Any question form, a request phrased as a question included ("can we pay off all our loans?")."""
    t = unicodedata.normalize("NFKC", text).strip()
    return bool(t) and bool(ASK_EN.search(t) or ASK_ZH.search(t) or re.search(r"^\s*(?:can|could)\s+(?:we|i)\b", t, re.IGNORECASE))


# ---- a Tier-3 subject in a question: information, or a request put as a question (ASK-1)
#
# A question that names a Tier-3 subject is a REQUEST unless it plainly asks for information, because a request written with
# a question mark ("sign a personal guarantee?", "should we pledge the equipment?", 要不要签个人担保？, "raise the discount limit
# to 5%?") must still reach the executor, be refused, be logged and raise its security event, as the same words without the
# mark do. The information reading is a narrow allowlist, owner only, and fails closed: anything not clearly information is
# a request. A message from any other caller is always a request.
#   information = ONE sentence that (a) asks about someone's attempt ("Did anyone try to change our limits?", 有人试图修改限额吗),
#   or (b) opens with a wh-word or an inverted auxiliary, or ends 吗 / 什么意思 ("Is equity an option?", "Does the bank want
#   collateral?", 个人担保是什么意思？), and (c) proposes nothing: no should/can/could, "to <act>", "-ing <act>", "what if",
#   "how do we", "is it ok to", 要不要 / 能不能 / 该不该, no second sentence.
TIER3_ATTEMPT = _re(r"\b(?:anyone|anybody|someone|somebody)\b.{0,25}\b(?:tr(?:y|ied|ying)|attempt\w*)\b",
                    r"\b(?:any|were there|was there|have there been)\b.{0,15}\battempts?\b", r"有人.{0,10}(?:试图|尝试|企图)")
_TIER3_ACTS = (r"sign|pledge|issue|sell|give|raise|lower|increase|decrease|change|edit|modify|update|override|bypass|ignore|"
               r"mortgage|grant|offer|post|put|use|take|go|do|add|cut|set|waive|remove|cancel|approve|accept|agree|pay|draw|repay")
_TIER3_ING = r"(?:sign|pledg|issu|sell|giv|rais|lower|increas|decreas|chang|edit|modif|updat|overrid|bypass|ignor|mortgag|grant|offer)ing"
TIER3_INFO_OPEN = _re(
    r"^\s*(?:(?:so|and|ok|okay|hey|hi|also|but|then|right|now|quick question|one question|question)[ ,:]+)*"
    r"(?:what|what['’]s|whats|which|who|who['’]s|when|where|why|how(?!\s+about\b)"
    r"|is|isn['’]t|are|aren['’]t|was|were|does|doesn['’]t|do|did|didn['’]t|has|hasn['’]t|have|haven['’]t|had)\b",
    r"(?:吗|么)\s*[?？。.!！~～]*\s*$", r"什么意思", r"是什么", r"什么是", r"是否|有没有|多少")
TIER3_PROPOSES = _re(
    r"\b(?:should|shall|must|ought|need to|needs to|have to|want to|wants to|would you|could you|can you|can we|could we|can i)\b",
    rf"\bto\s+(?:{_TIER3_ACTS})\b", rf"\b{_TIER3_ING}\b", r"\bwhat\s+(?:if|about|should)\b", r"\bhow\s+(?:do|can|could|should|would)\b",
    r"\bis it\s+(?:ok|okay|fine|worth|wise|safe|allowed|possible|permitted|a good idea)\b", r"\bgood idea\b", r"\bso\s+(?:you|we|that)\b",
    r"\bplease\b", r"\bgo ahead\b", r"要不要", r"能不能", r"可不可以", r"该不该", r"应不应该", r"应该", r"能否", r"可否", r"需不需要",
    r"是否(?:要|该|应|可以|能)", r"帮", r"麻烦", r"^\s*请", r"可以[^，。？?]{0,20}(?:吗|么)", r"能[^，。？?]{0,20}(?:吗|么)")


def tier3_is_information(text: str) -> bool:
    """Whether a question that names a Tier-3 subject only asks for information (see the block above). Fails closed."""
    t = unicodedata.normalize("NFKC", text).strip()
    if not t or re.search(r"[?？。!！;；]\s*\S|\.\s+\S", t):
        return False  # empty, or more than one sentence: whatever follows the question may be the request
    if TIER3_ATTEMPT.search(t):
        return True
    return bool(TIER3_INFO_OPEN.search(t)) and not TIER3_PROPOSES.search(t)


# Questions that a read cue would answer wrongly, each routed to ASK_BOOKS with its topic (rules.py, before the reads).
ASK_TOPICS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # "Do we have any capex contracts?", 有哪些设备采购合同: the contracts on file, not the built-in capex case
    ("capex_contracts", _re(
        r"\b(?:capex|purchase|equipment|machine|machinery)\s+(?:contracts?|agreements?|orders?|commitments?)\b",
        r"\bpurchases?\b.{0,25}\bcommitted\b", r"\bcommitted\b.{0,25}\bpurchases?\b",
        r"(?:设备|采购|购置|机器)[^，。?？]{0,6}(?:合同|协议)", r"承诺[^，。?？]{0,6}采购")),
    # "Does the plan breach any covenant?": the plan's pro forma, not today's status
    ("plan_covenants", _re(r"\b(?:plan|funding|draw|borrowing)\b.{0,40}\b(?:covenants?|breach\w*|dscr|leverage)\b",
                           r"(?:方案|融资|提款).{0,12}(?:契约|违约|违反|杠杆|覆盖)")),
    # "How much money has FLOW moved?", FLOW一共动了多少钱: the activity log, not the cash status
    ("money_moved", _re(r"\b(?:money|cash|funds?)\b.{0,25}\bmoved\b", r"\bmoved\b.{0,20}\b(?:money|cash|funds?)\b",
                        r"\bflow\b.{0,20}\b(?:moved|spent|paid out|transferred)\b",
                        r"(?:动|转|划)(?:了|过)?(?:多少|什么)?(?:钱|资金|款)", r"动过钱")),
    # "When does your mandate expire?", 授权什么时候到期, "What can FLOW do without me?": the signed mandate
    ("mandate", _re(r"\bmandate\b", r"\bwithout (?:me|my approval|asking me)\b", r"\bneeds? my approval\b",
                    r"\b(?:what|which)\b.{0,20}\b(?:limits?|authority|authori[sz]ed|allowed)\b",
                    r"授权(?!书)", r"(?:需要|要)我(?:批准|审批|同意)", r"不经过我", r"限额(?:是多少|有哪些|多少)")),
    # "How much would FLOW's plan cost?", FLOW的方案要花多少钱: the plan's cost, not the cash status
    ("plan_cost", _re(
        r"\b(?:plan|fixing the gap|closing the gap|covering the gap|the fix)\b.{0,20}\b(?:cost|costs|price|expensive)\b",
        r"\bcost\b.{0,20}\b(?:of|for) (?:the |flow['’]?s |your )?(?:plan|fix|fixing)\b",
        r"方案.{0,8}(?:多少钱|成本|费用|花多少)", r"(?:补上|补足|填补)?缺口.{0,6}(?:要)?花多少")),
    # "How much can we get for our invoices?", 我们的发票最多能融多少钱, "How much more can we borrow?": what can be raised
    # (a covenant's headroom, "how much more can we borrow before we break the leverage covenant?", is the ratios read)
    ("capacity", _re(r"^(?!.*\b(?:covenants?|leverage|dscr)\b)(?!.*(?:契约|杠杆)).*\bhow much\b(?!.{0,25}\bneed\b).{0,30}"
                     r"\b(?:borrow|get for|finance|advance)\b",
                     r"\bborrow against\b", r"\bhow much (?:more )?(?:credit|financing)\b",
                     r"(?:最多|还)能(?:融|借|贷)(?:多少|到)", r"能融多少", r"能借多少", r"(?:发票|应收).{0,8}(?:融资|融)(?:多少|吗)")),
    # "What's the break-even discount for early payment?": a definition, not an early-pay plan to send to the buyer
    ("break_even", _re(r"\bbreak[- ]?even\b", r"\babove what (?:discount|rate)\b", r"\btoo expensive\b", r"盈亏平衡",
                       r"超过多少.{0,6}(?:不划算|不值)", r"折扣.{0,8}(?:上限|最多多少|超过多少)")),
    # "How much do we need to raise to stay safe?", 要保持安全，我们需要融多少钱: the funding need, not the cash status
    ("fund", _re(r"\bhow much\b.{0,30}\b(?:need|have) to (?:raise|borrow|fund|find|cover)\b", r"\bhow much are we short\b",
                 r"需要(?:融|借|筹)(?:多少|资)", r"(?:要|得)(?:融|借|筹)多少", r"缺多少(?:钱)?")),
    # "What is causing the cash gap?", 资金缺口是怎么造成的: what drives the gap, not a plan to fund it
    ("why_short", _re(
        r"\b(?:why|what(?:['’]s| is)? caus\w*|what(?:['’]s| is)? driv\w*|reasons?)\b.{0,40}\b(?:short|gap|shortfall|low|run out|tight)\b",
        r"(?:缺口|不够|缺钱|紧张).{0,8}(?:怎么造成|为什么|原因|怎么来)", r"(?:为什么|为何).{0,12}(?:不够|缺口|缺钱|紧张|短缺)")),
    # "Any open negotiations?", 我们发过什么还价: what is open or was sent, not a counter to send
    ("deals", _re(r"\b(?:open|ongoing|pending|active|current)\s+(?:negotiations?|requests?|deals?|offers?|counters?)\b",
                  r"(?:在谈|谈判中|待处理)的?(?:交易|请求|报价)")),
    # "What counter did we send?", 我们发过什么还价: what was sent, not a counter to send now
    ("deals_sent", _re(r"\b(?:what|which|any)\b.{0,25}\b(?:counters?|counter-?offers?|offers?)\b.{0,15}\b(?:sent|made|offered)\b",
                       r"\bwhat did we (?:last )?(?:offer|counter|send|propose)\b",
                       r"(?:发过|发了|报过|提过|给过|上次).{0,6}(?:什么)?(?:还价|报价|条件|反报价)")),
    # "What is our DSO?", 应收账款周转天数是多少: the days to be paid, not a funding need (周转)
    ("receivable_days", _re(r"\bdso\b", r"\bdays sales outstanding\b", r"\bhow long\b.{0,30}\b(?:to pay|pay us|take to pay)\b",
                            r"周转天数", r"(?:平均)?多久(?:才)?(?:付款|回款|付钱|结款)")),
)
# The term debt ("When is our next loan payment?", 下一笔贷款还款是什么时候, "Can we pay off all our loans?"): asked about, it is
# not a repayment of a facility (REPAY_FACILITY repays a drawn line on demand; the equipment loan is repaid on its schedule).
DEBT_ASK = _re(r"\bdebts?\b", r"\b(?:term |equipment |bank )?loans?\b(?!\s+(?:options?|offers?|file|pack|package))",
               r"\bowe the bank\b", r"\bpay the bank\b", r"债务", r"负债", r"贷款(?!资料|材料|包|申请)", r"还贷", r"欠银行")

# Subjects the books do not hold (app/nl/ask.py says so and names the nearest thing FLOW can show).
NOT_HELD: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("vat", _re(r"\bvat\b", r"\binput tax\b", r"\breclaim\b.{0,10}\btax\b", r"增值税", r"进项税", r"销项税")),
    ("tax", _re(r"\btax(?:es)?\b", r"交税", r"纳税", r"税款", r"税务", r"多少税", r"缴税")),
    ("customer_profit", _re(
        r"\b(?:which|what) (?:customers?|buyers?|clients?)\b.{0,25}\b(?:profitable|profit|make us the most|margin)",
        r"\bmost profitable (?:customer|buyer|client)s?\b", r"哪个(?:客户|买家).{0,6}(?:最赚钱|利润|毛利)")),
    ("margin", _re(r"\bgross margin\b", r"\bmargins?\b", r"毛利")),
    ("profit", _re(r"\bprofit(?:s|able|ability)?\b", r"\bp&l\b", r"\bnet income\b", r"\bincome statement\b", r"利润", r"赚钱吗",
                   r"(?<!盈亏)盈利", r"(?<!资金)亏损")),
    ("revenue", _re(r"\brevenue\b", r"\bturnover\b", r"\bsales\b(?!\s+(?:tax|contract|pipeline))", r"营收", r"销售额", r"营业额",
                    r"收入多少")),
    ("inventory", _re(r"\binventory\b", r"\bstock\b(?!\s+market)", r"库存", r"存货")),
    ("pay_per_person", _re(r"\b(?:each|every|per) (?:employee|person|worker|head|staff member)\b",
                           r"\bby (?:person|employee|head)\b", r"每个(?:员工|人|工人)", r"按人")),
    ("staff", _re(r"\bheadcount\b", r"\bhow many (?:staff|employees|people|workers)\b", r"\bstaff\b",
                  r"\bhir(?:e|ing)\b(?!\s+purchase)",
                  r"\bmore (?:people|workers|staff)\b", r"员工", r"多少人", r"招人", r"工人")),
    ("accounts", _re(r"\b(?:each|every|all) (?:of )?(?:our )?(?:bank )?accounts\b", r"\bby (?:bank )?account\b",
                     r"\bper (?:bank )?account\b", r"\beach account\b", r"每个(?:银行)?账户", r"按账户", r"各个?账户")),
    ("payables", _re(r"\baccounts payable\b", r"\bpayables?\b", r"\bowe (?:our |the )?suppliers\b", r"欠供应商", r"应付账款",
                     r"应付款")),
    ("credit_rating", _re(r"\bcredit (?:rating|score)\b", r"\bwhat do (?:the )?banks think\b", r"信用评级", r"银行怎么(?:评价|看)")),
    ("market", _re(r"\bcompetitors?\b", r"\bcompetition\b", r"\bour market\b", r"\bin the market\b", r"\bindustry\b",
                   r"竞争对手", r"行业", r"行情")),
    ("fx", _re(r"\bexchange rates?\b", r"\bhedg\w*\b", r"\bdollars?\b", r"\bforex\b", r"汇率", r"对冲", r"外汇", r"美元")),
    ("valuation", _re(r"\b(?:company|business)\b.{0,10}\bworth\b", r"\bvaluation\b", r"\bvalued at\b",
                      r"\bworth\b.{0,10}\b(?:company|business)\b", r"公司值多少", r"估值")),
    ("past_spend", _re(r"\blast (?:month|year|quarter)\b.{0,30}\b(?:spend|spent|expenses?|cost)\b",
                       r"\b(?:spend|spent|expenses?)\b.{0,30}\blast (?:month|year|quarter)\b",
                       r"(?:上个月|去年|上季度).{0,8}(?:花|支出|开支|费用)")),
    ("social_insurance", _re(r"\bsocial insurance\b", r"\bemployee benefits\b", r"\bpensions?\b", r"社保", r"公积金")),
    ("products", _re(r"\bby product\b", r"\bproducts?\b.{0,20}\b(?:sell|best|backlog)\b", r"\bwhich products?\b", r"按产品",
                     r"哪个产品", r"产品.{0,6}(?:卖|毛利|销量)")),
)
NOT_HELD_PAY_PER_PERSON = dict(NOT_HELD)["pay_per_person"]
# EBITDA is held (one monthly figure): "What's our monthly operating profit?", 每月息税折旧前利润是多少
_HELD_FIGURE = _re(r"\bebitda\b", r"\boperating profit\b", r"息税折旧前")
_CAPEX_SUBJECT = _re(r"\b(?:machine\w*|equipment|investment|capex|purchase)\b", r"设备", r"机器", r"投资", r"购置")


# Whether the staff can be paid is the payroll in the forecast, which the books hold ("can I pay my staff this month?",
# 员工工资够不够发); what each person is paid is not.
_PAY_STAFF = _re(r"\b(?:pay|paying|cover|afford)\b.{0,20}\b(?:staff|employees|workers|people|team)\b",
                 r"\b(?:staff|employees|workers)\b.{0,20}\b(?:get paid|be paid|paid on time)\b",
                 r"(?:员工|工人).{0,4}(?:工资|薪水|薪资).{0,8}(?:够|发|付|能|有问题)", r"(?:发|付)(?:得起|得出).{0,8}(?:员工|工人|工资|薪水|薪资)",
                 r"(?:够|能).{0,6}(?:给员工|发员工)")


# Hiring is not the payroll on the books ("Can we afford two more workers?", 多招两个人): it stays not held.
_MORE_STAFF = _re(r"\b(?:more|new|another|extra|additional|two|three|hire|hiring)\b", r"招", r"新员工", r"多(?:请|雇)")


def not_held(text: str) -> str | None:
    """The subject the books do not hold that the text asks about (a NOT_HELD key), or None. A machine's or an
    investment's payback is held (the capex case), so "is the machine profitable?" is not a refusal; nor is whether the
    staff can be paid (the payroll)."""
    if _CAPEX_SUBJECT.search(text) or _HELD_FIGURE.search(text):
        return None
    if _PAY_STAFF.search(text) and not NOT_HELD_PAY_PER_PERSON.search(text) and not _MORE_STAFF.search(text):
        return None
    return next((key for key, pat in NOT_HELD if pat.search(text)), None)


# Asking for figures in a list ("Balance by account, please", 按账户列一下余额, "Break down the payroll by person"): a
# not-held subject asked for this way is answered like a question, which it is.
DATA_REQUEST = _re(r"^\s*(?:please\s+)?(?:list|show|tell|break\s*down|split)\b", r"\bby (?:account|person|employee|product)\b",
                   r"\bplease\.?\s*$", r"列一下", r"列出", r"按.{1,4}列", r"给我看", r"告诉我")
# The subjects of the books: an otherwise unmatched question about one of them goes to ASK_BOOKS (app/nl/ask.py answers it,
# or gives the nearest-capability reply exactly as before when it cannot).
BOOKS_TOPIC = _re(
    r"\b(?:cash|money|funds?|funding|financ\w*|debts?|loans?|lines?|credit|facilit\w*|banks?|invoices?|receivables?|customers?"
    r"|buyers?|suppliers?|payroll|wages?|salar\w*|payments?|pay|paid|owe\w*|mandate|limits?|reserve|floor|covenants?|dscr"
    r"|leverage|ebitda|plan|deals?|contracts?|offers?|counters?|negotiat\w*|approvals?|capex|machine\w*|equipment|tax\w*|vat"
    r"|profit\w*|margins?|revenue|sales|inventory|stock|staff|employees?|competitors?|interest|rates?|cost\w*|gap|short\w*"
    r"|runway|forecast|flow|foshan|dongguan|spend|spent|expenses?|headroom|budget|liquidity)\b",
    r"现金", r"钱", r"资金", r"融资", r"贷款", r"债", r"额度", r"授信", r"银行", r"发票", r"应收", r"应付", r"客户", r"买家",
    r"供应商", r"工资", r"付款", r"回款", r"欠", r"授权", r"限额", r"储备", r"契约", r"杠杆", r"方案", r"合同", r"报价", r"还价",
    r"审批", r"设备", r"机器", r"税", r"利润", r"毛利", r"营收", r"库存", r"员工", r"竞争", r"利率", r"成本", r"缺口", r"预测",
    r"佛山", r"东莞", r"账", r"支出", r"费用")
