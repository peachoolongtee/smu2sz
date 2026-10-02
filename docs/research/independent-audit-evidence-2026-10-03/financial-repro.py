from fractions import Fraction
from app.domain.fixtures import load_scenario
from app.domain.models import *
from app.domain.money import Ratio,post
from app.financial import project
from app.financial.concessions import value_concessions
from app.funding.rates import all_in_rate,break_even_cost_share
from app.financial.charges import finance_invoice_charges,upfront_fee
from app.capex.evaluate import evaluate_capex
from app.capex.models import CapexRequest,CapexCandidate
from tests.financial.builders import extension
s,m=load_scenario()
clean=s.model_copy(update={'flows':[],'receivables':[],'recurring_invoices':[],'debts':[],'facilities':[],'cash_fen':100_000_000,'monthly_ebitda_fen':10_000_000})
m=m.model_copy(update={'min_cash_fen':0,'min_dscr_bp':10000,'max_leverage_bp':100000,'max_apr_bp':100000})
base=next(f for f in s.facilities if f.kind==FacilityKind.EQUIPMENT_TERM_LOAN)
f=base.model_copy(update={'status':FacilityStatus.COMMITTED,'drawn_fen':12_000_000,'rate_bp':0,'term_months':12,'lead_time_days':0,'covenants':[]})
t=project(clean.model_copy(update={'facilities':[f],'as_of_day':61}),[],[],Mode.CONSERVATIVE,30,0)
print('CARRIED_AMORT',{'opening_actual':clean.cash_fen,'cash_before_today':t.days[60].closing_fen,'cash_today':t.days[61].closing_fen,'past_payment_days':[(p.day,[e.amount_fen for e in p.events]) for p in t.days if p.day<61 and p.events],'horizon':t.horizon_days})
# Horizons: identical invoice stream, identical horizon/bounded obligations apart from open-ended status.
for h in [90,180,365,730]:
 a=value_concessions([extension()],s,Ratio.of(Fraction(10,100)),'independent',h)[0]
 b=value_concessions([extension(duration=DurationKind.RECURRING_BOUNDED,invoices=h//30)],s,Ratio.of(Fraction(10,100)),'independent',h)[0]
 print('CONCESSION',h,'perpetual',a.value_fen,'bounded_same_count',b.value_fen,'ratio',Fraction(a.value_fen,b.value_fen) if b.value_fen else None)
# capex fee choice and existing drawn loan omissions.
loan0=base.model_copy(update={'id':'ZERO','status':FacilityStatus.COMMITTED,'rate_bp':0,'upfront_fee_bp':1000,'term_months':12,'lead_time_days':0,'covenants':[],'limit_fen':100_000_000})
loan1=loan0.model_copy(update={'id':'ONE','rate_bp':100,'upfront_fee_bp':0})
req=CapexRequest(price_fen=60_000_000,monthly_uplift_fen=2_000_000,uplift_start_month=1,life_months=60,candidates=[CapexCandidate(facility_id='ZERO',term_months=12),CapexCandidate(facility_id='ONE',term_months=12)],include_cash_line=False,extension_target_terms_days=None)
r=evaluate_capex(req,clean.model_copy(update={'facilities':[loan0,loan1]}),m)
print('CAPEX_FEE_CHOICE',r.selected_facility_id,[(x.facility_id,x.total_interest_fen,x.feasible) for x in r.structures],'omitted_upfront',6_000_000)
# Existing amortising draw of 1.2m requiring 100k/month, and proposed 600k loan requiring 50k/month;
# existing monthly EBITDA 100k +20k uplift -> actual DSCR .8; capex ignores existing facility service -> 2.4.
carried=loan1.model_copy(update={'id':'EXISTING','rate_bp':0,'drawn_fen':120_000_000,'limit_fen':120_000_000})
new=loan1.model_copy(update={'id':'NEW','rate_bp':0})
req=req.model_copy(update={'candidates':[CapexCandidate(facility_id='NEW',term_months=12)]})
r=evaluate_capex(req,clean.model_copy(update={'facilities':[carried,new]}),m)
print('CAPEX_EXISTING_DRAW',r.selected_facility_id,r.structures[0].dscr_by_month[0].dscr.value,'reported_leverage',r.structures[0].leverage.value,'actual_dscr',Fraction(12_000_000,15_000_000),'actual_leverage',Fraction(180_000_000,120_000_000))
# Front loaded fee annual basis vs realised amount, and invoice upfront duplicated across periods in break-even.
iff=next(f for f in s.facilities if f.kind==FacilityKind.INVOICE_FINANCING).model_copy(update={'upfront_fee_bp':100})
st=s.model_copy(update={'facilities':[iff]})
for d in [1,29,30,31,59,60,61,89,90,91]:
 c,k,p=break_even_cost_share(st,m,d)
 ints,fees,_=finance_invoice_charges(iff,10_000_000,d)
 actual=Fraction(ints+fees+upfront_fee(iff,10_000_000),10_000_000)
 print('IF_BREAK_EVEN',d,'estimated_share',float(c),'actual_share',float(actual),'difference_fen',post(c*10_000_000)-(ints+fees+upfront_fee(iff,10_000_000)))
# Bullet repayment actual monthly scheduled covenant vs synthetic level schedule.
bullet=base.model_copy(update={'id':'BULLET','status':FacilityStatus.COMMITTED,'drawn_fen':0,'rate_bp':500,'term_months':12,'repayment':Repayment.BULLET,'lead_time_days':0,'covenants':[],'limit_fen':100_000_000})
a=FundingAction(kind=FundingActionKind.DRAW,facility_id='BULLET',day=0,amount_fen=50_000_000)
t=project(clean.model_copy(update={'facilities':[bullet]}),[],[a],Mode.CONSERVATIVE,365,0)
mat=t.days[360]
print('BULLET_DSCR','reported',t.months[11].dscr.value,'cash_debt_service_at_maturity',-sum(e.amount_fen for e in mat.events),'actual_month_dscr',Fraction(clean.monthly_ebitda_fen,-sum(e.amount_fen for e in mat.events)))
from app.verifier.evaluate import _extension_pro_forma
for freq in [15,30,60,365]:
 st=s.model_copy(update={'recurring_invoices':[x.model_copy(update={'every_days':freq}) for x in s.recurring_invoices]})
 cv=value_concessions([extension()],st,Ratio.of(Fraction(10,100)),'independent',365)
 vs,ps,inputs=_extension_pro_forma([extension()],cv,st,m)
 correct=post(Fraction(cv[0].per_invoice_fen*365, freq*12))
 print('EXTENSION_MONTHLY_SERVICE',freq,'reported',inputs.get('extra_monthly_debt_service'),'annualized_monthly_correct_fen',correct)
# Same-basis: monthly annuity uses stated rate/12 but lease kind calls stated effective rate.
lease=next(f for f in s.facilities if f.kind==FacilityKind.EQUIPMENT_LEASE)
print('LEASE_RATE_CONVENTION',lease.rate_bp,'effective_annual_from_monthly',float((1+Fraction(lease.rate_bp,120000))**12-1))
# Capex cash path bypasses loan APR, borrowing flag and debt covenants.
line=next(f for f in s.facilities if f.kind==FacilityKind.CREDIT_LINE).model_copy(update={'covenants':[],'limit_fen':100_000_000,'rate_bp':5000,'lead_time_days':0})
st=clean.model_copy(update={'cash_fen':0,'facilities':[line]})
req=req.model_copy(update={'candidates':[],'include_cash_line':True})
mm=m.model_copy(update={'allow_new_borrowing':False,'max_apr_bp':100,'max_leverage_bp':100})
r=evaluate_capex(req,st,mm)
print('CAPEX_CASH_LINE_RULE_BYPASS',r.structures[0].feasible,'allow_new_borrowing',mm.allow_new_borrowing,'rate_bp',line.rate_bp,'max_apr_bp',mm.max_apr_bp,'reported_selected',r.selected_id)
from tests.financial.builders import ob,rebate
from app.mandate.predicates import check_concession_caps
futuregain=ob('FUTURE_GAIN',ObligationType.PRICE_ADJUSTMENT,rate_bp=100,effective_day=1000)
cost=rebate(rate_bp=150,cap_fen=40_000_000)
cv=value_concessions([futuregain,cost],s,Ratio.of(Fraction(10,100)),'independent',365)
base=project(s,[],[],Mode.CONSERVATIVE,365,m.min_cash_fen)
t=project(s,[futuregain,cost],[],Mode.CONSERVATIVE,365,m.min_cash_fen)
print('FUTURE_GAIN_OFFSET',[v.value_fen for v in cv],'cash_increment_by365',t.days[365].closing_fen-base.days[365].closing_fen,'cap5000_pass',not check_concession_caps([futuregain,cost],cv,s,m.model_copy(update={'max_aggregate_forward_concession_fen':500_000}),'BUYER-1'))
for e in [0,-1,-10_000_000]:
 try:
  evaluate_capex(req,st.model_copy(update={'monthly_ebitda_fen':e}),mm)
  print('NONPOSITIVE_EBITDA',e,'returned')
 except Exception as ex:
  print('NONPOSITIVE_EBITDA',e,type(ex).__name__,str(ex))
from app.funding.menu import menu_row
from app.funding.search import Search
from app.funding.rates import early_pay_rate
fep=next(f for f in s.facilities if f.kind==FacilityKind.BUYER_EARLY_PAY)
ss=s.model_copy(update={'as_of_day':20})
row=menu_row(fep,ss,m)
print('MENU_TENOR',float(row.all_in_rate.value),'actual_at_today_rate',float(early_pay_rate(Fraction(fep.rate_bp,10000),10)))
