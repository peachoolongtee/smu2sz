"""The broad, deterministic fallback for the owner's top questions: what the literal patterns in `answers.QUESTIONS` miss.

Offline there is no model to catch unusual wording ("can my company survive this month?", 我们会不会断现金流), so the
matching itself must be broad. Here a question is normalised (typos and casual spellings fixed), read for topic cues in
English and Chinese (survive / make it / stay afloat / run out / broke -> cash safety; staff / salaries / wages -> payroll;
owe / borrow / loan -> debt; 撑 / 断 / 周转 / 资金链 -> cash safety; 工资 -> payroll; 欠 / 贷款 -> debt ...), and every
question is scored by weighted cues. Only a clear winner is returned: a score of at least `MIN_SCORE` and `MIN_MARGIN` above
the next one; anything else is None, so the caller routes or refuses it as before.

Pure text: no store, no state, nothing written. The time window a question names ("this month", "the next 6 months",
未来半年) is read here too (`window_days`), for the answers that take one.
"""

from __future__ import annotations

import re
import unicodedata

from app.nl import lexicon as lx

MIN_SCORE = 3.0
MIN_MARGIN = 1.0

# ---------------------------------------------------------------- normalising

_TYPOS: tuple[tuple[str, str], ...] = (
    (r"\b(?:buisness|busines|bussiness|bussines|buisiness)\b", "business"),
    (r"\b(?:quater|quartr|qaurter|quaters)\b", "quarter"),
    (r"\b(?:compnay|comapny|compny|companys)\b", "company"),
    (r"\b(?:mony|monney|moeny)\b", "money"),
    (r"\b(?:enought|enuf|enogh|enugh)\b", "enough"),
    (r"\b(?:surive|survie|survivie|servive)\b", "survive"),
    (r"\b(?:payrol|pyroll)\b", "payroll"),
    (r"\b(?:salarys|salaires)\b", "salaries"),
    (r"\b(?:emploees|employes|employess)\b", "employees"),
    (r"\b(?:finacial|financal|finanical)\b", "financial"),
    (r"\b(?:liquidty|liqudity)\b", "liquidity"),
    (r"\b(?:monht|mnth|montth)\b", "month"),
    (r"\b(?:recieve|recive)\b", "receive"),
    (r"\bcash-?flow\b", "cash flow"),
    (r"\bwhats\b", "what's"), (r"\bwats\b", "what's"), (r"\bhows\b", "how's"),
    (r"\bgonna\b", "going to"), (r"\bwanna\b", "want to"), (r"\bgotta\b", "have to"),
    (r"\bcant\b", "can't"), (r"\bdont\b", "don't"), (r"\bwont\b", "won't"), (r"\bim\b", "i'm"),
    (r"^r\b", "are"), (r"\br (?=we|u|you|they)\b", "are "), (r"\bu\b", "you"), (r"\bur\b", "your"),
    (r"\bpls\b|\bplz\b", "please"), (r"\bthru\b", "through"), (r"\btil\b|\btill\b", "until"),
)
_TYPO_RES = tuple((re.compile(p), s) for p, s in _TYPOS)


def canon(text: str) -> str:
    """Lower case, NFKC, straight quotes, the usual typos and casual spellings fixed, spaces collapsed."""
    q = unicodedata.normalize("NFKC", text).replace("’", "'").replace("‘", "'").lower().strip()
    for pat, sub in _TYPO_RES:
        q = pat.sub(sub, q)
    return re.sub(r"\s+", " ", q)


# ---------------------------------------------------------------- question form


_ASKS = re.compile(
    r"[?？]|\b(?:what|how|when|who|which|why|can|could|should|is|are|am|do|does|did|will|would|any|have|has|must)\b"
    r"|吗|么|呢|吧\s*[?？]?\s*$|多少|哪|谁|什么|怎么|怎样|如何|为什么|为何|能不能|是否|几|会不会|够不够|是不是|有没有|行不行|要不要"
    r"|([\u4e00-\u9fff])不\1"
    r"|可不可以|撑得住|得过来|得过去|没问题吧")
# An advice request without a question form: "Give me some advice on our cash flow", "help me keep cash healthy", 给点建议
_ADVICE_REQUEST = re.compile(
    r"^\s*(?:please\s+)?(?:give me|tell me how|help me|advise|any tips|some tips|tips)\b|\badvice\b|\btips\b|给点.{0,8}建议|给我.{0,6}建议")
# An instruction, or a request addressed to FLOW to do something: never answered by the broad reading (the literal patterns
# and the rules keep their reading of it, unchanged).
_COMMAND_EN = re.compile(
    r"^\s*(?:please\s+)?(?:draw|repay|pay off|pay back|fund|finance|send|accept|reject|approve|decline|counter|offer|negotiate|record|"
    r"book|apply|transfer|move|go ahead|run it|execute|cancel|confirm|sign|pledge|issue|change|set|give|chase|remind|email|call|"
    r"get|make|stop|start|switch|turn|raise|lower|increase|decrease|borrow|take|use|buy|sell)\b")
_COMMAND_ZH = re.compile(
    r"^\s*(?:请)?(?:提款|还款|偿还|融资|发送|接受|拒绝|批准|还价|记录|执行|取消|确认|签|抵押|修改|转账|申请|给|帮我(?:提|还|借|融|付|发|签))")
_ACTION = re.compile(
    r"\b(?:draw(?:ing)?|drawdown|negotiat\w*|counter[- ]?offer|haggle|transfer|pledge|wire)\b|\bapprove (?:it|this|that|the plan|apr)"
    r"|^\s*(?:please\s+)?(?:can|could|would|will) (?:you|flow) (?!tell|show|explain|advise|help me understand)\w+"
    r"|提款|支取|还价|谈判|转账|抵押|动用.{0,4}(?:授信|额度|信用)|帮我(?!看|说|分析|想想|讲)")
_ABOUT_A_DEAL = re.compile(r"\b(?:offers?|deals?|accept\w*|contracts?|agreements?|quotes?|buyers? (?:wants?|says?|asks?))\b"
                           r"|合同|协议|报价|交易|(?<!贷款)条款|接受|买家说|要求我们")


def asks(q: str) -> bool:
    """Whether the (canonical) text asks something, or asks for advice, and is not an instruction or a request to act."""
    if not q or len(q) > 400:
        return False
    if _COMMAND_EN.search(q) and not _ADVICE_REQUEST.search(q):
        return False
    if _COMMAND_ZH.search(q) and not (_ASKS.search(q) or _ADVICE_REQUEST.search(q)):
        return False
    if _ACTION.search(q):
        return False
    return bool(_ASKS.search(q) or _ADVICE_REQUEST.search(q))


# ---------------------------------------------------------------- cues

_CUES: dict[str, str] = {
    # cash survival, enough on its own: survive, make it, stay afloat, run out of money, broke, a cash crunch; 撑 / 断 / 资金链 / 周转
    "surv": r"\bsurviv\w*|\bmake it\b|\bstay(?:ing)? afloat\b|\bafloat\b|\bkeep (?:the lights on|going|running)\b|\bgo(?:ing)? (?:broke|bust|under)\b"
            r"|\bbroke\b|\bbust\b|\bbankrupt\w*|\binsolven\w*|\bsolven\w*|\brun(?:s|ning)? out of (?:money|cash|funds)\b|\brun(?:s|ning)? dry\b"
            r"|\bcash crunch\b|\bcrunch\b|\bable to pay (?:our |the |all )?(?:bills|suppliers)\b|\bpay (?:our |the |all )?bills\b"
            r"|\bclose (?:down|the doors)\b|\bkeep the business going\b"
            r"|撑|挺过|熬过|断(?:现金流|流|链|裂|粮)|资金链|周转|活下去|活得下去|倒闭|破产|没钱|钱紧|紧不紧",
    # safety words that need a subject (our cash, the company, we): "are we in trouble", "is our cash safe", 资金安全
    "safe": r"\bsafe(?:ly)?\b|\bsafety\b|\btrouble\b|\bdanger\b|\bat risk\b|\brisky?\b|\bliquid\b|\bhealthy\b|\bsecure\b"
            r"|安全|出问题|没问题|缺口|风险|稳|健康",
    "ok": r"\b(?:ok|okay|alright|all right|fine|enough|good shape|worried|worry|in good shape)\b|够不够|够用|够吗|不够|还好吗|好吗",
    "subject": r"\b(?:company|business|firm|we|us|our|we're)\b|公司|我们|咱们|企业",
    "cash": r"\bcash\b|\bmoney\b|\bcash flow\b|\bliquidity\b|\bbalance\b|\bfunds\b|\bfinances?\b|\bfinancial(?:ly)?\b|\bbills\b|\bbank account\b"
            r"|\bcash-?wise\b|\bmoney[- ]wise\b|现金|钱|资金|账上|余额|现金流|财务",
    "window": r"\b(?:this|next|the|coming|rest of the) (?:week|month|quarter|year|half|half year|couple of (?:weeks|months)|few (?:weeks|months))\b"
              r"|\b(?:next|coming) \d+ (?:days?|weeks?|months?)\b|\b\d+ (?:days?|weeks?|months?)\b|\bhalf (?:a )?year\b|\byear[- ]end\b"
              r"|\bend of (?:the )?(?:month|quarter|year)\b|\buntil\b|\bdecember\b|\bfor now\b"
              r"|这个月|本月|下个月|月底|季度|半年|年底|今年|未来|接下来|这周|本周|下周|\d+\s*(?:天|个月|周)|[一二两三四五六七八九十]+个?(?:月|周|星期)",
    "howto": r"\bhow (?:do|can|should|could|would|will|must) (?:i|we)\b|\bhow to\b|\bwhat (?:should|can|do|must|could) (?:i|we) (?:do|be doing)\b"
             r"|\bwhat (?:steps|actions|measures)\b|\badvi[cs]e\b|\btips?\b|\bwhat would you do\b|\bbest (?:thing|move)\b|\bsmartest\b"
             r"|\bpriorit\w*|\bhelp me\b|\bmake sure\b|\bensure\b|\bguarantee\b|\bprotect\w*|\bavoid\w*|\bsecure\b|\bimprove\b"
             r"|\bkeep (?:\w+ ){0,3}(?:safe|healthy|positive|afloat|going|solvent)\b|\bstay (?:safe|afloat|solvent)\b"
             r"|\bshould i be doing\b|\btell me how\b|\bmanage\b|\bget through\b"
             r"|怎么(?:保证|确保|办|做|避免|管|才能|样才)|如何|怎样|该怎么|应该(?:做|怎么)|该做|要做(?:些)?什么|做些什么|办法|建议|确保|保证|避免|怎么办"
             r"|保住|才稳|管钱|管理",
    "when": r"\bwhen\b|\bwhat day\b|\bwhich day\b|\bhow soon\b|\bhow long\b|\bhow many (?:days|weeks|months)\b|\bdate\b"
            r"|什么时候|哪天|哪一天|多久|几天|几个月|多少天|到什么时候|何时",
    "runout": r"\brun(?:s|ning)? out\b|\bhit zero\b|\bbroke\b|\blast\b|\bleft\b|\bzero\b|花光|没钱|用完|还能用|能用多久|撑多久|撑几|撑到",
    "arrive": r"\b(?:get|receive|collect)\b.{0,12}\b(?:money|cash|funds|paid)\b|\barriv\w*|\bcome in\b|\bland\b|拿到|到账|收到|回款",
    "low": r"\blowest\b|\bworst\b|\bbottom\b|\btightest\b|\bhow low\b|\blow point\b|最低|最少|最紧",
    "reserve": r"\breserve\b|\bminimum (?:cash|balance)\b|\bmin cash\b|\bfloor\b|\bbuffer\b|\bcushion\b|\bsafety net\b|\bthreshold\b"
               r"|储备|安全线|最低余额|底线|警戒线",
    "below": r"\bbelow\b|\bunder\b|\bdip\w*|\bdrop\w*|\bbreach\w*|\bfall\w*|低于|跌破|跌到|低过",
    "spend": r"\bspend\w*|\bspare\b|\bfree (?:cash|money)\b|\btake out\b|\bdiscretionary\b|能花|闲钱|可以用|能动用|支出多少|还能支出|可以花",
    "outgo": r"\bbills?\b|\bpayments?\b|\boutgoings?\b|\boutflows?\b|\bexpenses?\b|\bgoing out\b|\bpay out\b|\bdue\b|\bspending\b"
             r"|支出|付款|要付|付哪些|开支",
    "upcoming": r"\bcoming up\b|\bupcoming\b|\bsoon\b|\bnext (?:few )?(?:weeks?|month)\b|\bahead\b|\bthis month\b|\bover the next\b"
                r"|最近|接下来|即将|这个月|近期",
    "ability": r"\b(?:able to|can (?:we|i)|will (?:we|i)|enough)\b|能不能|够不够|发得出|付得起",
    "payroll": r"\bpayroll\b|\bwages?\b|\bsalar(?:y|ies)\b|\bstaff\b|\bemployees?\b|\bworkers?\b|\bpay (?:everyone|everybody|people|the team|my team)\b"
               r"|工资|薪水|薪资|发薪|员工|工人|薪酬",
    "why": r"\bwhy\b|\bhow come\b|\bwhat(?:'s| is)? (?:causing|driving|draining|behind|eating)\b|\breasons?\b|\bcaus\w*|\bdrain\w*"
           r"|为什么|为何|原因|怎么会|怎么回事",
    "short": r"\bshort\w*|\btight\b|\blow\b|\bgap\b|\bdrop\w*|\brun(?:ning)? (?:low|out)\b|不够|缺钱|紧张|缺口|短缺|紧",
    "need": r"\bhow much\b.{0,30}\bneed\b|\bgap\b|\bshortfall\b|\bshort by\b|\braise\b|\bextra (?:cash|money)\b|\btop up\b|\bborrow to\b"
            r"|缺口|差多少|缺多少|需要.{0,4}融|融多少|需要多少钱",
    "cheapest": r"\bcheapest\b|\bcheaper\b|\bwhich way\b|\bwhat way\b|\bmarginal\b|哪种|哪个渠道|最划算|最便宜|最省|边际",
    "recommend": r"\bbest way\b|\bhow (?:should|do|can|could) we (?:fund|cover|close|fill|fix|bridge)\b|\brecommend\w*|\bsuggest\w*|\badvi[cs]e\b"
                 r"|\bplan\b|\bproposal\b|\bpropos\w*|建议|推荐|方案|怎么补|如何补",
    "plan": r"\bplan\b|\bproposals?\b|\brecommended\b|\byour fix\b|\bflow's (?:funding|financing)\b|方案|计划",
    "cost": r"\bcosts?\b|\bfees?\b|\bexpensive\b|\bprice\b|\bcharges?\b|成本|多少钱|费用|花多少|代价",
    "debt": r"\bdebts?\b|\bloans?\b|\bborrow\w*|\bowe\b|\bindebted\b|\blenders?\b|\bthe bank\b|\binterest\b|\bcredit\b|\binstal?ments?\b"
            r"|\brepayments?\b|\bfinancing\b|\bfacilit\w*|欠|贷款|负债|债务|还贷|借款|借|贷|授信|还款|利息",
    "loan": r"\bloans?\b|\bdebts?\b|\brepayments?\b|\binstal?ments?\b|\bthe bank\b|还贷|贷款|还款",
    "owe_total": r"\bindebted\b|\bin debt\b|负债|欠了多少|一共欠",
    "total": r"\btotal\b|\bin all\b|\baltogether\b|\boutstanding\b|\bhow much\b|一共|总共|总|多少",
    "monthly": r"\bmonth(?:ly)?\b|\beach month\b|\bevery month\b|\bper month\b|\binterest\b|每月|每个月|月供|利息",
    "payoff": r"\bpay (?:off|back|down)\b|\bclear\b|\brepay (?:everything|all|it all)\b|\bdebt[- ]free\b|\bget rid of\b|\bsettle\b|还清|清偿|还完|结清",
    "capacity": r"\bmore\b|\bavailable\b|\broom\b|\bleft\b|\bunused\b|\bcapacity\b|\bstill\b|\bif we need\b|\bspare\b|还能|还有多少|没用|剩|可用|额度",
    "apply": r"\bapply\w*|\bapplication\b|\bprepare\b|\bneed from us\b|\bdocuments?\b|\bpaperwork\b|申请|材料|资料|准备",
    "line_zero": r"\bat zero\b|\bclean[- ]?down\b|\bclear(?:ed)? (?:the )?line\b|清零",
    "breakeven": r"\bbreak[- ]?even\b|\btoo expensive\b|\babove what\b|盈亏平衡|超过多少",
    "next": r"\bnext\b|\bupcoming\b|下次|下一笔|下一次|下个",
    "customer": r"\bcustomers?\b|\bclients?\b|\bbuyers?\b|\bdebtors?\b|\bfoshan\b|\bdongguan\b|客户|佛山|东莞|买家",
    "owes_us": r"\bowes? us\b|\bowed\b|\bunpaid\b|\breceivables?\b|\bdebtor\b|欠我们|欠款|应收|欠钱最多|谁欠",
    "most": r"\bmost\b|\blargest\b|\bbiggest\b|\btop\b|最多|最大",
    "late": r"\blate\b|\boverdue\b|\bon time\b|\bpast due\b|\bdelay\w*|\bhasn't paid\b|\bhaven't paid\b|晚|拖欠|逾期|推迟|延迟|拖",
    "depend": r"\bdepend\w*|\breliant\b|\breliance\b|\brely\b|\brelying\b|\bconcentrat\w*|\bbiggest customer\b|\blose\b|\bone customer\b"
              r"|\bcomes? from\b|依赖|集中|占比|占多少",
    "whatif": r"\bwhat if\b|\bwhat happens\b|\bif\b|\bsuppose\b|要是|如果|假如|万一",
    "early": r"\bearly[- ]?pay\w*|\bpay(?:s|ing)? early\b|\bearly settlement\b|提前付款|提前结算",
    "discount": r"\bdiscount\b|折扣",
    "waiting": r"\bwaiting\b|\battention\b|\bon my plate\b|\bdeal with\b|\bto[- ]?do\b|\bneed to do\b|\bmy desk\b|需要我处理|处理|要做什么|待办|我要做",
    "approve": r"\bapprov\w*|\bsign[- ]?off\b|\bpermission\b|审批|批准|批的|签字|要我批",
    "pending": r"\bpending\b|\bwaiting\b|\banything\b|\bqueue\b|待|有没有|有.{0,4}吗",
    "terms": r"\b\d{1,3}[- ]?days?\b|\bterms\b|账期",
    "covenant": r"\bcovenants?\b|\bdscr\b|\bleverage\b|\bloan conditions\b|\bbank conditions\b|\bcomplian\w*|\bebitda\b|\bratios?\b"
                r"|契约|贷款条款|合规|杠杆|倍数|比率",
    "inside": r"\binside\b|\bwithin\b|\bcompliant\b|\bcompliance\b|\bok\b|\bokay\b|\bfine\b|\bmet\b|\bmeet\w*|\bbreach\w*|\bsafe\b"
              r"|符合|违反|满足|达标|没问题",
    "breakcov": r"\bbreak\w*|\bbreach\w*|\bviolat\w*|\bput us in\b|违反|突破|不达标|违约",
    "probe": r"\bwhat would\b|\bwhat could\b|\bhow close\b|\bbefore we\b|\bhow much more\b|\bhow far\b|什么情况|多少.{0,4}才|多近|还能(?:再)?借多少|前提下",
    "planword": r"\bplan\b|\bfunding\b|\bfinancing\b|\bproposal\b|方案|融资",
    "machine": r"\bmachines?\b|\bequipment\b|\bdie[- ]cutting\b|\bcapex\b|设备|机器",
    "activity": r"\bdid (?:you|flow)\b|\bhas flow done\b|\bhave you done\b|\bdone lately\b|\blately\b|\brecently\b|\bwithout asking\b"
                r"|\byou(?:'ve| have) been doing\b|\bwhat (?:has|have) (?:flow|you)\b|做了什么|做了哪些|最近.{0,6}操作|干了什么|做过什么",
    "yesno": r"^\s*(?:so |and |honestly,? |be honest,? )?(?:are|is|will|can|could|do|does|am|have|has|would|should)\b|会不会|能不能|吗\s*[?？]?\s*$"
             r"|([一-鿿])不\1",
    "advise_me": r"\bwhat would you do\b|\bin my (?:position|shoes)\b|\bwhat do you advise\b|换作你|如果你是我",
    "mandate": r"\ballowed\b|\bon (?:your|its) own\b|\bwithout me\b|\bauthority\b|\bauthori[sz]\w*|\bpermitted\b|\bdecide\b|\bmandate\b"
               r"|不用我|无需我|自己做|自己能|自己去|可以自己|自己可以|flow自己|你自己|权限|授权|不经过我",
    "needme": r"\bneeds? (?:me|my)\b|\bmyself\b|\bhave to approve\b|\brequire (?:me|my)\b"
              r"|需要我(?:批准|签字|同意|决定)|(?<!不用)(?<!无需)(?<!不经过)我(?:签字|批准)",
}
CUES: dict[str, re.Pattern[str]] = {k: re.compile(v) for k, v in _CUES.items()}
# Not a question about money at all, whatever words it shares with one: the security log, data, passwords.
_ELSEWHERE = re.compile(r"\bsecurity\b|\bhack\w*|\battack\w*|\bpassword\w*|\bdata\b|\bprivacy\b|\bsystem\b.{0,10}\bsafe\b|安全事件|安全日志|黑客|攻击|密码|数据安全|隐私")

# question id -> (anchors: at least one group must be fully present, weights by cue)
_TABLE: dict[str, tuple[tuple[tuple[str, ...], ...], dict[str, float]]] = {
    "LIQ-01": ((("surv",), ("safe", "cash"), ("safe", "subject"), ("ok", "cash"), ("ok", "window")),
               {"surv": 3, "safe": 2, "ok": 1.5, "cash": 1, "window": 1, "howto": -4, "when": -2, "why": -3, "cost": -2, "payroll": -2,
                "debt": -1.5, "customer": -1.5, "low": -1.5, "reserve": -1, "spend": -2.5, "need": -1, "covenant": -3,
                "machine": -3, "recommend": -1.5, "runout": -0.5, "yesno": 1, "arrive": -2}),
    "LIQ-03": ((("runout",), ("when", "surv")),
               {"when": 2, "runout": 2.5, "cash": 1, "surv": 0.5, "howto": -4, "low": -1, "reserve": -0.5, "payroll": -2,
                "debt": -2, "outgo": -1, "why": -2, "yesno": -1, "arrive": -3}),
    "LIQ-04": ((("low",),), {"low": 3, "cash": 1, "when": 0.5, "window": 0.5, "howto": -3, "debt": -2, "why": -2, "cost": -2}),
    "LIQ-05": ((("reserve", "below"), ("reserve", "when")), {"reserve": 3, "below": 2, "when": 1, "cash": 0.5, "howto": -3, "low": -1}),
    "LIQ-06": ((("spend",),), {"spend": 3, "cash": 0.5, "total": 0.5, "howto": -2, "outgo": -0.5}),
    "LIQ-09": ((("outgo",),), {"outgo": 2.5, "upcoming": 1.5, "cash": 0.5, "when": 0.5, "ability": -2, "late": -3, "payroll": -1.5,
                               "howto": -3, "debt": -1, "surv": -1, "customer": -2.5, "arrive": -3}),
    "LIQ-10": ((("payroll",),), {"payroll": 4, "ok": 1, "surv": 0.5, "safe": 0.5, "cash": 0.5, "window": 0.5, "howto": -3, "ability": 0.5}),
    "LIQ-14": ((("why", "short"), ("why", "cash")), {"why": 3, "short": 2, "cash": 1}),
    "LIQ-15": ((("need",),), {"need": 3, "total": 1, "cash": 0.5, "reserve": 0.5, "surv": 0.5, "ok": 0.5, "recommend": -1, "cost": -2,
                              "yesno": -2, "howto": -1.5, "cheapest": -3}),
    "FUN-02": ((("recommend",),), {"recommend": 3, "planword": 1, "cash": 0.5, "need": 0.5, "cost": -3, "covenant": -3,
                                   "machine": -3, "howto": -0.5, "cheapest": -2, "apply": -3}),
    "FUN-04": ((("cost", "plan"),), {"cost": 3, "plan": 2, "recommend": 1, "terms": -3, "machine": -3, "monthly": -2, "cheapest": -3}),
    "DEBT-01": ((("debt", "total"), ("owe_total",)),
                {"debt": 3, "total": 1.5, "owe_total": 1.5, "monthly": -2, "payoff": -3, "capacity": -2, "next": -2, "covenant": -5,
                 "customer": -2, "owes_us": -4, "need": -2, "planword": -1, "cost": -1, "when": -1, "apply": -3, "cheapest": -3,
                 "mandate": -3, "line_zero": -4}),
    "DEBT-03": ((("debt", "monthly"),), {"debt": 2, "monthly": 3, "total": 0.5, "apply": -3}),
    "DEBT-04": ((("payoff",),), {"payoff": 3, "debt": 2}),
    "DEBT-06": ((("debt", "capacity"),), {"debt": 2, "capacity": 2.5, "total": 0.5, "payoff": -2, "monthly": -1, "next": -1,
                                          "covenant": -3, "apply": -3, "mandate": -3, "line_zero": -4}),
    "DEBT-08": ((("loan", "next"), ("loan", "when")), {"next": 2, "loan": 2.5, "when": 1.5, "outgo": 1, "total": -0.5, "line_zero": -4,
                                                       "apply": -3}),
    "CUS-01": ((("owes_us",),), {"owes_us": 3, "customer": 1.5, "most": 1.5, "late": -1.5, "when": -2}),
    "CUS-03": ((("late",),), {"late": 3, "customer": 1.5, "outgo": 0.5, "owes_us": 0.5, "whatif": -3}),
    "CUS-05": ((("depend",),), {"depend": 3, "customer": 1.5}),
    "CUS-07": ((("whatif", "late"),), {"whatif": 2, "late": 2.5, "customer": 1.5}),
    "CUS-08": ((("early",),), {"early": 3, "discount": 1, "customer": 0.5, "mandate": -3, "breakeven": -4}),
    "DEAL-01": ((("waiting",),), {"waiting": 3, "approve": -1}),
    "DEAL-02": ((("approve",),), {"approve": 3, "pending": 1.5, "needme": -1.5, "mandate": -2}),
    "DEAL-09": ((("terms", "cost"),), {"terms": 2.5, "cost": 2.5, "customer": 1}),
    "COV-01": ((("covenant", "inside"),), {"covenant": 3, "inside": 1, "probe": -3, "planword": -3}),
    "COV-05": ((("covenant", "breakcov", "probe"),), {"covenant": 2, "breakcov": 2, "probe": 1.5, "planword": -3}),
    "COV-07": ((("covenant", "planword"),), {"covenant": 2.5, "planword": 2.5, "breakcov": 1, "inside": 1}),
    "ACT-01": ((("activity",),), {"activity": 3}),
    "MAN-01": ((("mandate",),), {"mandate": 3.5, "needme": -1.5, "approve": -0.5}),
    "MAN-02": ((("needme",),), {"needme": 3, "approve": 1.5, "mandate": -2}),
    "general_advice": ((("howto", "cash"), ("howto", "surv"), ("howto", "safe"), ("howto", "payroll"), ("howto", "window"), ("advise_me",)),
                       {"howto": 3, "advise_me": 3, "surv": 1.5, "safe": 1.5, "ok": 1, "cash": 1.5, "window": 1, "payroll": 0.5,
                        "recommend": 0.5, "cost": -2, "covenant": -2, "machine": -2, "customer": -1, "debt": -1, "why": -2,
                        "cheapest": -2, "apply": -2}),
}
# Questions whose answer is about a deal or an invoice anyway; every other answer is the owner's own cash, never an offer's.
_DEAL_TOPICS = frozenset({"CUS-01", "CUS-03", "CUS-05", "CUS-07", "CUS-08", "DEAL-01", "DEAL-02", "DEAL-09"})
# A named amount ("the cheapest way to raise ¥200,000", 要借20万) is not the funding need, the debt or FLOW's plan.
_NOT_WITH_AN_AMOUNT = frozenset({"LIQ-15", "FUN-02", "FUN-04", "DEBT-01", "DEBT-03", "DEBT-04", "DEBT-06", "DEBT-08"})


def cues(q: str) -> set[str]:
    return {name for name, pat in CUES.items() if pat.search(q)}


def scores(q: str) -> dict[str, float]:
    """Each question's score on the canonical text (only questions whose anchors are present)."""
    if _ELSEWHERE.search(q):
        return {}
    hit = cues(q)
    out: dict[str, float] = {}
    deal = bool(_ABOUT_A_DEAL.search(q))
    amount = bool(lx.amounts(q))
    for qid, (anchors, weights) in _TABLE.items():
        if not any(all(a in hit for a in group) for group in anchors):
            continue
        if (deal and qid not in _DEAL_TOPICS) or (amount and qid in _NOT_WITH_AN_AMOUNT):
            continue
        out[qid] = sum(w for cue, w in weights.items() if cue in hit)
    return out


# The reads that already answer these subjects right keep them: the financing comparison ("Which of our facilities is
# cheapest?"), the capex case with its structures ("Lease or loan for the machine?", "Does the investment pay off?"), a deal
# with a buyer, the borrower file and the reconciliation.
_DEFER = re.compile(r"\b(?:machine\w*|machinery|equipment|investment|capex|purchase|lease)\b|设备|机器|投资|购置|租赁")
_DEFER_READS = (lx.COMPARE_FINANCING, lx.DEAL, lx.BORROWER_FILE, lx.RECONCILE)


def best(question: str) -> str | None:
    """The one question this text clearly asks, by its cues, or None (no clear winner, not a question, an instruction, or a
    subject another read answers)."""
    q = canon(question)
    if not asks(q) or _DEFER.search(q) or (not CUES["covenant"].search(q) and any(p.search(q) for p in _DEFER_READS)):
        return None
    ranked = sorted(scores(q).items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < MIN_SCORE:
        return None
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < MIN_MARGIN:
        return None
    return ranked[0][0]


# ---------------------------------------------------------------- the time window asked about

_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十二": 12}
_UNIT_DAYS = {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30, "year": 365, "years": 365,
              "天": 1, "日": 1, "周": 7, "星期": 7, "个星期": 7, "月": 30, "个月": 30, "年": 365}


def window_days(question: str) -> int | None:
    """The forecast window a question names, in days from today: "this month" and "the next 30 days" -> 30, "this quarter" -> 90,
    "the next 6 months" / 未来半年 -> 180, "until year end" / 年底 -> 365 (longer than any forecast). None when it names none."""
    q = canon(question)
    m = re.search(r"\b(?:next|coming|following|for|over|within|in) (?:the )?(?:next )?(\d{1,3}) ?(days?|weeks?|months?|years?)\b", q)
    if m is None:
        m = re.search(r"\b(\d{1,3}) ?(weeks?|months?|years?)\b", q)
    if m is not None:
        return int(m.group(1)) * _UNIT_DAYS[m.group(2)]
    m = (re.search(r"(?:未来|接下来|今后|往后|最近|近|这)(\d{1,3}|十二|[一两二三四五六七八九十])\s*(个月|个星期|星期|周|天|日|年)", q)
         or re.search(r"(?<![哪每第晚拖\d])(\d{1,3}|十二|[一两二三四五六七八九十])\s*(天|日)(?:之内|以内|内)", q)
         or re.search(r"(?<![哪每第晚拖\d])(\d{1,3}|十二|[一两二三四五六七八九十])\s*(个月|个星期|星期|周|年)", q))
    if m is not None and not re.search(r"(?:晚|拖|延迟|推迟|账期)\s*" + re.escape(m.group(0)), q):
        n = int(m.group(1)) if m.group(1).isdigit() else _ZH_NUM[m.group(1)]
        return n * _UNIT_DAYS[m.group(2)]
    words: tuple[tuple[str, int], ...] = (
        (r"\byear[- ]end\b|\bend of (?:the )?year\b|\brest of the year\b|\bthis year\b|\buntil december\b|\bdecember\b|年底|今年|年末", 365),
        (r"\bhalf (?:a )?year\b|\bsix months\b|半年|六个月", 180),
        (r"\b(?:this|next|the|coming) quarter\b|\bend of (?:the )?quarter\b|\bthree months\b|季度", 90),
        (r"\bcouple of months\b|\btwo months\b|\bfew months\b|两个月", 60),
        (r"\bnext month\b|下个月|下月", 60),
        (r"\b(?:this|the|coming) month\b|\bend of (?:the )?month\b|\bmonth[- ]end\b|这个月|本月|月底|这月", 30),
        (r"\b(?:couple|few) (?:of )?weeks\b|\btwo weeks\b|两周|两个星期", 14),
        (r"\b(?:this|next|the coming) week\b|这周|本周|下周|这个星期", 7),
    )
    for pat, n in words:
        if re.search(pat, q):
            return n
    return None


__all__ = ["CUES", "MIN_MARGIN", "MIN_SCORE", "asks", "best", "canon", "cues", "scores", "window_days"]
