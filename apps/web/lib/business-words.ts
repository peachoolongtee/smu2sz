import type { I18n } from "./i18n";
import { whenText } from "./when";

/**
 * Business pages speak in distances from today, never "day N". Some server sentences (executor summaries, counter texts,
 * option notes) still carry day numbers; this rewrites those references for display. It counts days only (INVARIANT 13
 * is about money) and never touches an amount. Demo views keep the server's words unchanged.
 */
export function plainDays(text: string, today: number, t: I18n["t"]): string {
  if (!text) return text;
  const rel = (day: number) => day - today;
  // A date range in brackets repeats the duration already stated ("held 10 days (day 37 to day 47)"): drop it.
  let out = text.replace(/\s*\((?:from )?day \d+ (?:to|until) (?:day \d+|in \d+ days?|today|tomorrow)\)/g, "");
  out = out.replace(/\bon or before day (\d+)\b/g, (_, d: string) => {
    const n = rel(Number(d));
    return n > 1 ? t("biz.when.within", { n }) : t("biz.when.by", { when: whenText(Number(d), today, t) });
  });
  out = out.replace(/\b(until|by|before|after|from) day (\d+)\b/g, (_, prep: string, d: string) => {
    const n = rel(Number(d));
    const phrase = n === 0 ? t("biz.when.today") : n === 1 ? t("biz.when.tomorrow") : n === -1 ? t("biz.when.yesterday") : n > 0 ? t("biz.when.fromToday", { n }) : t("biz.when.daysAgo", { n: -n });
    return `${prep} ${phrase}`;
  });
  out = out.replace(/\bon day (\d+)\b/g, (_, d: string) => whenText(Number(d), today, t));
  // Counted words the server writes as "2 day(s)", and its status codes, read as plain words.
  out = out.replace(/\b(\d+) (day|invoice|message|round)\(s\)/g, (_, n: string, w: string) => `${n} ${w}${n === "1" ? "" : "s"}`);
  out = out.replace(/\bstill OPEN\b/g, "still unpaid");
  out = out.replace(/\b([Dd])ay (\d+)\b/g, (_, first: string, d: string) => {
    const s = whenText(Number(d), today, t);
    return first === "D" ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  });
  return out;
}

/**
 * Ids in a server sentence become the names on the books. An id is replaced only as a whole token, so "BUYER-1" inside
 * an invoice id such as "RI:BUYER-1:2" stays as it is.
 */
export function idsToNames(text: string, named: { id: string; name: string }[]): string {
  let out = text;
  for (const { id, name } of named) {
    if (!id || id === name) continue;
    const esc = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(`(?<![\\w:-])${esc}(?![\\w:-])`, "g"), name);
  }
  return out;
}

/** The first letter in upper case, for a server reason shown as a sentence of its own. */
export function sentenceCase(text: string | null | undefined): string {
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Names on the books (facilities, scheduled cash events) and a few alert titles are stored in English; in Chinese mode the
 * Business pages show them in Chinese. Names only, longest first, never an amount: every figure stays as the server wrote it.
 */
const ZH_NAMES: [RegExp, string][] = [
  [/Invoice financing \(onboarded platform\)/g, "发票融资（已接入平台）"],
  [/Government-guaranteed working-capital loan/g, "政府担保流动资金贷款"],
  [/Existing equipment loan/g, "现有设备贷款"],
  [/Bank acceptance bill discounting/g, "银行承兑汇票贴现"],
  [/Buyer early-payment offer/g, "买方提前付款"],
  [/Owner equity or outside investor/g, "股东或外部投资"],
  [/Equipment term loan/g, "设备定期贷款"],
  [/Equipment lease/g, "设备租赁"],
  [/Bank credit line/g, "银行信用额度"],
  [/Invoice financing/g, "发票融资"],
  [/Debt service \(principal\)/g, "偿还本金"],
  [/Payroll, month (\d+)/g, "第 $1 个月工资"],
  [/Payroll/g, "工资"],
  [/Supplier payment/g, "供应商付款"],
  [/Operating bill/g, "运营账单"],
  [/Reserve headroom thin (.+)$/g, "储备余量偏紧（$1）"],
  [/Reserve breach ahead (.+)$/g, "将跌破储备（$1）"],
  [/Funding in transit/g, "在途资金"],
  [/Mandate expiring/g, "授权书即将到期"],
  // Common executor and reconciliation sentences.
  [/^Drew (¥[\d,.]+) on (.+?)(?: (today|yesterday|\d+ days? ago|in \d+ days?))?$/g, "从$2提款 $1 $3"],
  [/Queued for owner approval \((APR-\d+)\)/g, "已提交老板审批（$1）"],
  [/agreed early payment for (¥[\d,.]+) of face/g, "约定提前付款，抵扣面值 $1"],
  [/the agreed (¥[\d,.]+) for (\S+) arrived/g, "约定的 $1（$2）已到账"],
  [/outstanding from (.+?) was due (.+?) and is still unpaid\./g, "（$1）应于$2到账，至今未付。"],
  [/the cash lands (in \d+ days?) after the (\d+)-day lead time, not today/g, "资金在$2天准备期后于$1到账，而非今天"],
  [/Advance (¥[\d,.]+) on the (¥[\d,.]+) invoice to (.+?) due (.+?) from (.+?) today/g, "以$3的 $2 发票（$4到期）向$5融资 $1，今天"],
  // Distances from today the server wrote in English.
  [/\bin (\d+) days?\b/g, "$1 天后"],
  [/\b(\d+) days? ago\b/g, "$1 天前"],
  [/\btoday\b/g, "今天"],
  [/\btomorrow\b/g, "明天"],
  [/\byesterday\b/g, "昨天"],
];

export function localNames(text: string | null | undefined, lang: string): string {
  if (!text) return text ?? "";
  if (lang !== "zh") return text;
  let out = text;
  for (const [re, zh] of ZH_NAMES) out = out.replace(re, zh);
  return out;
}
