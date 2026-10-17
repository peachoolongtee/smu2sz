/**
 * Live implementations of the client functions in ../api.ts. Routes whose response already matches the
 * mock shape are plain passthroughs; the rest go through an adapter in this folder. Adapters rename and
 * fill fields from server strings; none of them computes money.
 */

import { DEMO_BUYER_KEYS } from "../config";
import type { ExposureContext } from "../api";
import { buyerExposureQuery } from "./exposure-query";
import { ApiError } from "../errors";
import { contextQuery, type CustomerContext } from "../customer-href";
import { serverScenario } from "../selection";
import type {
  AcceptRequest,
  AcceptResult,
  AddCustomerRequest,
  AddCustomerResponse,
  BuyerAcceptedRequest,
  BuyerAcceptedResult,
  BuyerDeclinedRequest,
  BuyerDeclinedResult,
  BuyerMessageView,
  BuyerReplyRequest,
  BuyerReplyResult,
  OfferedRequest,
  OfferedResult,
  WithdrawRequest,
  WithdrawResult,
  DeclineResult,
  ActivityView,
  DemoRestoreResult,
  DemoStoryView,
  ActRequest,
  AlertActResult,
  AlertsView,
  ClockView,
  ApprovalView,
  AuditView,
  BankReceiptResult,
  BorrowerFileRequest,
  BorrowerFileView,
  BuyerExposureView,
  ChaseView,
  AddToMenuResult,
  BuyEstimate,
  BuySideEvaluationView,
  BuyTimeline,
  CapexApplyRequest,
  CapexApplyResult,
  CapexPlansRequest,
  CapexPlansView,
  CapexRequest,
  CapexView,
  EligibilityView,
  FinanceHealthView,
  HealthInputsRequest,
  PurchaseCommitResult,
  PurchaseRow,
  PurchasesView,
  CompareView,
  DealsContext,
  EnvelopeView,
  ExposureView,
  ContractFixture,
  ContractTermsResult,
  ContractTermsView,
  CustomerOverviewView,
  InputSaveRequest,
  InputSaveResult,
  InputSheetView,
  CustomersView,
  DealsView,
  DocumentDecision,
  DocumentsList,
  DocumentView,
  FundingView,
  HomeView,
  LedgerView,
  MandateView,
  NavCounts,
  Mode,
  NegotiateRequest,
  NegotiationView,
  NlOpenerResponse,
  NlRequest,
  NlResponse,
  OfferPictureView,
  PictureScenario,
  OfferView,
  OperationView,
  PlanRequest,
  PilotJournalView,
  PriceCurveView,
  ReceivablesRead,
  ReceivablesWorthView,
  RecordReceiptRequest,
  RecordReceiptResult,
  ReconciliationView,
  StateView,
  SubmitDocumentRequest,
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
  WhatIfParams,
  WhatIfResult,
  WhatIfScope,
  WhatIfUnscoped,
  WorklistView,
  ApprovalDecision,
  SetupDocument,
  SetupDraft,
  SetupOpenResult,
  SetupPreview,
  SetupStatus,
} from "../types";
import * as approvals from "./approvals";
import * as decisions from "./decisions";
import { downloadFile, http } from "./http";
import * as trajectory from "./trajectory";

const enc = encodeURIComponent;

/** A strategy read the server has switched off (403 FEATURE_DISABLED) or does not have (404) is no data, not a failure: the card hides. */
async function nullWhenOff<T>(read: () => Promise<T>): Promise<T | null> {
  try {
    return await read();
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || (e.status === 403 && /FEATURE_DISABLED/.test(JSON.stringify(e.detail ?? e.message))))) return null;
    throw e;
  }
}

/**
 * A route the server does not have: FastAPI's own `{"detail": "Not Found"}` 404, which no handler of ours raises (every 404 of ours carries a code or a
 * sentence). Only this is "the server has no such read"; any other 404, a refusal or a failure is an error the page must show, not a reason to fall back.
 */
async function nullWhenRouteAbsent<T>(read: () => Promise<T>): Promise<T | null> {
  try {
    return await read();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404 && e.detail === "Not Found") return null;
    throw e;
  }
}

/** /negotiate returns the executor's raw results; the ledger view adds who asked and a one-line summary. */
function asOperationView(o: Record<string, unknown>): OperationView {
  return {
    ...o,
    day: (o.day as number | undefined) ?? (o.effective_day as number | undefined) ?? 0,
    requested_by: (o.requested_by as OperationView["requested_by"] | undefined) ?? null,
    summary: (o.summary as string | undefined) ?? (o.message as string | undefined) ?? "",
  } as unknown as OperationView;
}

/** The query of a reset or restore: its own parameters, then the stale-page guard (`from_scenario`, and `confirm_loss=1` only when the caller was told what is lost). */
function guardQuery(own: Record<string, string>, guard?: { from: string; confirm?: string }): string {
  const q = new URLSearchParams(own);
  if (guard) {
    q.set("from_scenario", guard.from);
    if (guard.confirm) q.set("confirm_loss", guard.confirm);
  }
  return q.toString();
}

export const live = {
  downloadFile,
  getState: () => http<StateView>("GET", "/state"),
  verifyOwnerToken: async (token: string): Promise<void> => {
    await http("GET", "/state", { token, silent: true });
  },
  getMandate: () => http<MandateView>("GET", "/mandate"),

  submitOffer: (req: SubmitOfferRequest) =>
    http<OfferView>("POST", "/offers", {
      body: req.fixture_id ? { fixture_id: req.fixture_id } : { counterparty_id: req.counterparty_id, documents: req.documents },
    }),

  /** GET /offers/{id} (owner): the offer, its documents, the latest verdict id and the deal's record id. An unknown id is a 404 the page explains. */
  getOffer: async (offerId: string, lang: "en" | "zh" = "en"): Promise<OfferView> => {
    try {
      return await http<OfferView>("GET", `/offers/${enc(offerId)}${lang === "zh" ? "?lang=zh" : ""}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, `Offer ${offerId} was not found. Submit it again from the Inbox.`, e.detail, "offer_missing", { id: offerId });
      throw e;
    }
  },

  evaluateOffer: (offerId: string, fixtureId?: string, lang: "en" | "zh" = "en") =>
    http<VerdictView>("POST", `/offers/${enc(offerId)}/evaluate${lang === "zh" ? "?lang=zh" : ""}`, { body: fixtureId ? { fixture_id: fixtureId } : {} }),

  negotiate: async (offerId: string, req: NegotiateRequest): Promise<NegotiationView> => {
    const n = await http<NegotiationView>("POST", `/negotiate/${enc(offerId)}`, { body: req });
    return { ...n, operations: n.operations.map((o) => asOperationView(o as unknown as Record<string, unknown>)) };
  },

  /** POST /offers/{id}/accept and /decline (accept as asked): the verdict and books version the owner was shown; a 409 refuses with the server's words and moves nothing. */
  acceptOffer: (offerId: string, req: AcceptRequest) => http<AcceptResult>("POST", `/offers/${enc(offerId)}/accept`, { body: req }),
  declineOffer: (offerId: string, req: AcceptRequest) => http<DeclineResult>("POST", `/offers/${enc(offerId)}/decline`, { body: req }),

  /** The message to the buyer for one counter (ADR-0011 addendum): `lang` is the buyer's language (the message), `uiLang` the page's (every word around it). */
  getBuyerMessage: (offerId: string, counterId: string, lang: "en" | "zh", uiLang: "en" | "zh") =>
    http<BuyerMessageView>("GET", `/offers/${enc(offerId)}/counters/${enc(counterId)}/message?lang=${lang}&ui_lang=${uiLang}`),
  /** "I've sent it to the buyer": bound to the verdict, the books and the exact message the owner copied; a 409 refuses with the server's words and records nothing. */
  markOffered: (offerId: string, counterId: string, req: OfferedRequest) => http<OfferedResult>("POST", `/offers/${enc(offerId)}/counters/${enc(counterId)}/offered`, { body: req }),
  buyerAccepted: (offerId: string, counterId: string, req: BuyerAcceptedRequest) =>
    http<BuyerAcceptedResult>("POST", `/offers/${enc(offerId)}/counters/${enc(counterId)}/buyer-accepted`, { body: req }),
  withdrawOffered: (offerId: string, counterId: string, req: WithdrawRequest) =>
    http<WithdrawResult>("POST", `/offers/${enc(offerId)}/counters/${enc(counterId)}/offered/withdraw`, { body: req }),
  buyerDeclined: (offerId: string, counterId: string, req: BuyerDeclinedRequest) =>
    http<BuyerDeclinedResult>("POST", `/offers/${enc(offerId)}/counters/${enc(counterId)}/buyer-declined`, { body: req }),
  buyerReply: (offerId: string, req: BuyerReplyRequest) => http<BuyerReplyResult>("POST", `/offers/${enc(offerId)}/buyer-reply`, { body: req }),

  planFunding: (req: PlanRequest, lang: "en" | "zh" = "en") => http<FundingView>("POST", lang === "zh" ? "/router/plan?lang=zh" : "/router/plan", { body: req }),

  getTrajectory: (mode: Mode, verdict?: VerdictView | null): Promise<TrajectoryView> => trajectory.getTrajectory(mode, verdict),

  getLedger: (lang: "en" | "zh" = "en") => http<LedgerView>("GET", `/ledger${lang === "zh" ? "?lang=zh" : ""}`),
  getAudit: () => http<AuditView>("GET", "/audit"),

  getActivity: (lang: "en" | "zh", ctx: { customer?: string | null; decision?: string | null; invoice?: string | null; path?: string | null; from?: string | null } = {}) => {
    const q = new URLSearchParams({ lang });
    for (const k of ["customer", "decision", "invoice", "path", "from"] as const) if (ctx[k]) q.set(k, ctx[k] as string);
    return http<ActivityView>("GET", `/activity?${q}`);
  },
  getDemoStory: (lang: "en" | "zh", seen?: string | null) => http<DemoStoryView>("GET", `/demo/story?lang=${lang}${seen ? `&seen=${encodeURIComponent(seen)}` : ""}`),
  restoreDemo: (lang: "en" | "zh", guard?: { from: string; confirm?: string }) => http<DemoRestoreResult>("POST", `/demo/restore?${guardQuery({ lang }, guard)}`, { body: {} }),

  getDecisions: (q: decisions.DecisionQuery) => decisions.getDecisions(q),
  getDecision: (id: string, lang: "en" | "zh") => decisions.getDecision(id, lang),

  getApprovals: (): Promise<ApprovalView[]> => approvals.getApprovals(),
  getApprovalsRead: () => approvals.getApprovalsRead(),
  decideApproval: (id: string, decision: ApprovalDecision) => approvals.decideApproval(id, decision),

  capexEvaluate: (req: CapexRequest) => http<CapexView>("POST", "/capex/evaluate", { body: req }),
  capexApply: (req: CapexApplyRequest) => http<CapexApplyResult>("POST", "/capex/apply", { body: req }),
  borrowerFile: (req: BorrowerFileRequest) => http<BorrowerFileView>("POST", "/borrower-file", { body: req }),

  getAlerts: () => http<AlertsView>("GET", "/alerts"),
  /** The owner's home read: written by the server in the language asked for; the owner token is required. */
  getHome: (lang: "en" | "zh", sinceDay: number | null = null) =>
    http<HomeView>("GET", `/home?lang=${lang}${sinceDay !== null ? `&since_day=${sinceDay}` : ""}`),
  /** GET /worklist: Home V2's right panel, in the language asked for. Null when the route is absent (404) or refused (403), as for an older server. */
  getWorklist: (lang: "en" | "zh", sinceDay: number | null = null) =>
    nullWhenOff(() => http<WorklistView>("GET", `/worklist?lang=${lang}${sinceDay !== null ? `&since_day=${sinceDay}` : ""}`)),
  /** GET /customers/{id}/overview with Home V2's selections: `decision` and `scenario` come back validated in `context.deal` and `context.scenario` (null when they do not name this buyer's deal). */
  getCustomerFocus: (id: string, lang: "en" | "zh", sel: { decision?: string | null; scenario?: string | null } = {}) =>
    http<CustomerOverviewView>("GET", `/customers/${enc(id)}/overview?lang=${lang}${sel.decision ? `&decision=${enc(sel.decision)}` : ""}${sel.scenario ? `&scenario=${enc(sel.scenario)}` : ""}`),
  /** GET /offers/{offer_id}/exposure for a Home V2 deal focus: the customer in the query asks for the echoed selections. Null when the feature is off or the offer is unknown. */
  getDealExposure: (offerId: string, lang: "en" | "zh", customer: string) =>
    nullWhenOff(() => http<ExposureView>("GET", `/offers/${enc(offerId)}/exposure?lang=${lang}&customer=${enc(customer)}`)),
  /** GET /home with a decision: the chart's title for that deal (`home_v2.chart.scenario_title_text`), null when the server has none. */
  getDealTitle: async (decision: string, lang: "en" | "zh"): Promise<string | null> =>
    (await http<HomeView>("GET", `/home?lang=${lang}&decision=${enc(decision)}`)).home_v2?.chart.scenario_title_text ?? null,
  /** GET /customers (flag `home_v2`): the same customers with the terms a page filters them by. Null when the flag is off or the route is absent. */
  getCustomers: (lang: "en" | "zh") => nullWhenOff(() => http<CustomersView>("GET", `/customers?lang=${lang}`)),
  getReconciliation: async (): Promise<ReconciliationView> => {
    const raw = await http<{ reconciliation: ReconciliationView; last_read_when?: string }>("GET", "/reconciliation");
    // The freshness word sits beside the report or inside it, depending on the server's version; the report carries whichever there is.
    return raw.reconciliation.last_read_when || !raw.last_read_when ? raw.reconciliation : { ...raw.reconciliation, last_read_when: raw.last_read_when };
  },

  /** GET /receivables/{id}/chase: the collection handoff for one open invoice (owner only; 404 unknown, 422 when nothing is outstanding). */
  getChase: (receivableId: string, lang: "en" | "zh") => http<ChaseView>("GET", `/receivables/${enc(receivableId)}/chase?lang=${lang}`),

  /** GET /cash/price-curve (flag `price_curve`). Null when the feature is off or absent. */
  getPriceCurve: (lang: "en" | "zh") => nullWhenOff(() => http<PriceCurveView>("GET", `/cash/price-curve?lang=${lang}`)),
  /** GET /receivables (owner only, no flag): the rows with what each invoice nets, who governs it and what to do next. Null on a server without the route (404), so the old page stands. */
  getReceivables: (lang: "en" | "zh") => nullWhenRouteAbsent(() => http<ReceivablesRead>("GET", `/receivables?lang=${lang}`)),
  /** GET /decisions/{id}/exposure (flag `exposure`): the buyer's late-payment test for a deal decision. Null when the feature is off or the decision names no buyer. */
  getDecisionExposure: (decisionId: string, lang: "en" | "zh") =>
    nullWhenOff(() => http<BuyerExposureView>("GET", `/decisions/${enc(decisionId)}/exposure?lang=${lang}&spare=0`)),
  /** GET /buyers/{id}/exposure (flag `exposure`). Null when the feature is off (404) or the buyer is unknown. The context (customer, invoice, decision, path, from) asks for `context.back`. */
  getBuyerExposure: (buyerId: string, lang: "en" | "zh", context: ExposureContext = {}) =>
    nullWhenOff(() => http<BuyerExposureView>("GET", `/buyers/${enc(buyerId)}/exposure?${buyerExposureQuery(lang, context)}`)),
  /** GET /receivables/worth (flag `collections_worth`). Null when the feature is off or absent. */
  getReceivablesWorth: (lang: "en" | "zh") => nullWhenOff(() => http<ReceivablesWorthView>("GET", `/receivables/worth?lang=${lang}`)),

  /** GET /buyers/{buyer_id}/envelope (flag `envelope`). Null when the feature is off or the buyer is unknown. The zone is a detail of the answer, read only when asked. */
  getEnvelope: (buyerId: string, lang: "en" | "zh", zone = false) =>
    nullWhenOff(() => http<EnvelopeView>("GET", `/buyers/${enc(buyerId)}/envelope?lang=${lang}${zone ? "&zone=1" : ""}`)),

  /** GET /offers/{offer_id}/exposure (flag `exposure`). Null when the feature is off, the offer is unknown or the route is absent. One read carries every path. */
  /** GET /offers/{id}/scenarios: the Cash impact tab's Business consequences (empty with the exposure off); its own read, not the picture's. */
  getOfferScenarios: async (offerId: string, lang: "en" | "zh"): Promise<PictureScenario[]> => (await http<{ scenarios: PictureScenario[] }>("GET", `/offers/${enc(offerId)}/scenarios?lang=${lang}`)).scenarios ?? [],
  getOfferExposure: (offerId: string, lang: "en" | "zh") => nullWhenOff(() => http<ExposureView>("GET", `/offers/${enc(offerId)}/exposure?lang=${lang}`)),

  /** GET /offers/{offer_id}/compare (flag `exposure`). Null when the feature is off, the route is absent or the offer has no verdict yet (404). */
  getOfferCompare: (offerId: string, lang: "en" | "zh") => nullWhenOff(() => http<CompareView>("GET", `/offers/${enc(offerId)}/compare?lang=${lang}`)),

  /** GET /pilot/journal (flag `pilot_journal`). Null when the feature is off or absent. Read-only: the web never posts an entry. */
  getPilotJournal: () => nullWhenOff(() => http<PilotJournalView>("GET", "/pilot/journal")),

  /** POST /nl. The owner channel sends X-Owner-Token. A buyer turn never carries the owner token; in a demo build it
   * sends the buyer's published channel key (X-Counterparty-Key), otherwise nothing, and the API treats it as a proposal. */
  nl: (req: NlRequest, opts: { business?: boolean } = {}): Promise<NlResponse> =>
    http<NlResponse>("POST", "/nl", {
      body: req,
      business: opts.business && req.actor !== "COUNTERPARTY",
      auth: req.actor === "COUNTERPARTY" ? "none" : "owner",
      buyerKey: req.actor === "COUNTERPARTY" ? DEMO_BUYER_KEYS[req.counterparty_id ?? ""] : undefined,
    }),

  /** POST /nl/session/reset: ends one chat session. The owner's with the owner token (passed in, so a sign-out can end it before the token
   * goes), a buyer's with its demo channel key; silent, so a refusal never opens the sign-in dialog. */
  endNlSession: async (sessionId: string, actor: NlRequest["actor"], counterpartyId?: string, token?: string | null): Promise<void> => {
    const buyer = actor === "COUNTERPARTY";
    // A buyer without a demo key (FastCapital) speaks anonymously, and ends its anonymous session the same way.
    const buyerKey = buyer ? DEMO_BUYER_KEYS[counterpartyId ?? ""] : undefined;
    await http("POST", "/nl/session/reset", {
      body: { session_id: sessionId },
      auth: buyer ? "none" : "owner",
      buyerKey,
      token: buyer ? undefined : (token ?? undefined),
      silent: true,
    });
  },

  /** POST /nl/opener. Owner only (the API answers 403 without the token, which opens the sign-in dialog). */
  nlOpener: (sessionId: string | undefined, lang: "en" | "zh"): Promise<NlOpenerResponse> =>
    http<NlOpenerResponse>("POST", "/nl/opener", { body: { session_id: sessionId, lang }, ownerOn403: true }),

  /** GET /clock needs no credential. */
  clock: async (): Promise<ClockView> => ({ day: (await http<{ day: number }>("GET", "/clock", { auth: "none" })).day, message: null }),

  /** POST /clock/advance {days}: the owner token (or the bank-feed key) is required; 403 opens the sign-in dialog. */
  advanceClock: async (days: number): Promise<ClockView> => {
    const r = await http<{ day: number; result: { message?: string } | null }>("POST", "/clock/advance", { body: { days }, ownerOn403: true });
    return { day: r.day, message: r.result?.message ?? null };
  },

  /** POST /alerts/{id}/act: executes the alert's cure as the agent. The body always binds the act to what was shown (409 ALERT_CHANGED when the books moved). */
  actOnAlert: (id: string, bound: ActRequest) => http<AlertActResult>("POST", `/alerts/${enc(id)}/act`, { body: bound, ownerOn403: true }),

  /** POST /whatif on the invoice of the negotiation addressed (`offer_id` in the body; none: the books' first buyer with a recurring invoice), the words in `lang`. A buyer the sandbox cannot value as a whole answers `available: false` and says why. */
  whatIf: (params: WhatIfParams, scope: { offerId?: string | null; lang?: "en" | "zh" } = {}) =>
    http<WhatIfResult | WhatIfUnscoped>("POST", `/whatif?lang=${scope.lang ?? "en"}`, { body: scope.offerId ? { ...params, offer_id: scope.offerId } : params }),

  /** GET /whatif/presets on the addressed negotiation's invoice: `available`, `invoice_text` and `scope_text` say which invoice the sandbox would act on, or why it has none (then no presets). */
  whatIfScope: (offerId: string, lang: "en" | "zh" = "en") =>
    http<WhatIfScope>("GET", `/whatif/presets?offer_id=${enc(offerId)}&lang=${lang}`),

  demoReset: async (scenario?: string, guard?: { from: string; confirm?: string }): Promise<void> => {
    // Loading another company (the busy books) is a long write: it gets the long timeout, not the default 20 s.
    const q = guardQuery(scenario ? { scenario } : {}, guard);
    await http("POST", q ? `/demo/reset?${q}` : "/demo/reset", { body: {}, timeoutMs: scenario ? 60_000 : undefined });
  },

  /** The guided Demo's synthetic bank event (owner, demo mode): the server posts the promised early payment as the bank feed would. */
  demoBankReceipt: () => http<BankReceiptResult>("POST", "/demo/bank-receipt", { body: {} }),

  /**
   * The owner records a payment they received: the existing typed RECEIVE_PAYMENT operation through POST /operations as the owner (Tier 1, the
   * owner's receipt is a fact). The mandate version is the stored one's (the executor checks only its signature for an owner's receipt); the day
   * is left to the server (today on its clock). The answer carries the server's words for what it did (`receipt`).
   */
  recordReceipt: async (req: RecordReceiptRequest, lang: "en" | "zh"): Promise<RecordReceiptResult> => {
    const mandate = await http<MandateView>("GET", "/mandate");
    const op = `owner-receipt-${req.key}`;
    return http<RecordReceiptResult>("POST", `/operations?lang=${lang}`, {
      body: {
        kind: "RECEIVE_PAYMENT", op_id: op, idempotency_key: op, mandate_version: mandate.mandate.version, requested_by: "OWNER",
        receivable_id: req.receivable_id, amount_fen: req.amount_fen, ...(req.bank_reference ? { bank_reference: req.bank_reference } : {}),
      },
    });
  },

  getEvidence: () => http<string>("GET", "/evidence", { as: "text" }),

  // contract ingestion (brief 03): every route needs the owner token; the responses already have the page's shape
  getDeals: (lang: "en" | "zh" = "en", ctx: DealsContext = {}) => {
    const q = new URLSearchParams();
    if (lang === "zh") q.set("lang", "zh");
    for (const k of ["customer", "invoice", "decision", "path", "from"] as const) if (ctx[k]) q.set(k, ctx[k] as string);
    return http<DealsView>("GET", `/deals${q.size ? `?${q}` : ""}`);
  },
  getDocuments: (lang: "en" | "zh" = "en") => http<DocumentsList>("GET", `/documents${lang === "zh" ? "?lang=zh" : ""}`),
  getDocument: async (id: string, lang: "en" | "zh" = "en"): Promise<DocumentView> =>
    (await http<{ document: DocumentView }>("GET", `/documents/${enc(id)}${lang === "zh" ? "?lang=zh" : ""}`)).document,
  submitDocument: async (req: SubmitDocumentRequest): Promise<DocumentView> =>
    (await http<{ document: DocumentView }>("POST", "/documents", { body: req })).document,
  // The answer's words (the outcome card, the reading) are written in the owner's language.
  decideDocument: (id: string, decision: "confirm" | "reject", docHash: string, linkFacilityId: string | null, lang: "en" | "zh" = "en") =>
    http<DocumentDecision>("POST", `/documents/${enc(id)}/${decision}${lang === "zh" ? "?lang=zh" : ""}`, {
      body: linkFacilityId ? { doc_hash: docHash, link_facility_id: linkFacilityId } : { doc_hash: docHash },
    }),
  refileDocument: async (id: string, counterpartyId: string, docHash: string, lang: "en" | "zh"): Promise<DocumentView> =>
    (await http<{ document: DocumentView }>("POST", `/documents/${enc(id)}/refile?lang=${lang}`, { body: { counterparty_id: counterpartyId, doc_hash: docHash } })).document,
  addCustomer: (body: AddCustomerRequest, lang: "en" | "zh") => http<AddCustomerResponse>("POST", `/customers?lang=${lang}`, { body }),
  getContractFixtures: async (): Promise<ContractFixture[]> => (await http<{ contracts: ContractFixture[] }>("GET", "/fixtures/contracts")).contracts,
  // ADR-0014: a confirmed customer contract's terms set up in the books (FEATURE_CONTRACT_TERMS). Switched off, the read answers 403
  // FEATURE_DISABLED and the step is not shown.
  getContractTerms: async (id: string, lang: "en" | "zh" = "en"): Promise<ContractTermsView | null> => {
    try {
      return (await http<{ terms: ContractTermsView }>("GET", `/documents/${enc(id)}/terms${lang === "zh" ? "?lang=zh" : ""}`)).terms;
    } catch (e) {
      if (e instanceof ApiError && e.status === 403 && (e.detail as { code?: unknown } | undefined)?.code === "FEATURE_DISABLED") return null;
      throw e;
    }
  },
  setUpContractTerms: (id: string, docHash: string, termsHash: string, lang: "en" | "zh" = "en") =>
    http<ContractTermsResult>("POST", `/documents/${enc(id)}/terms${lang === "zh" ? "?lang=zh" : ""}`, { body: { doc_hash: docHash, terms_hash: termsHash } }),
  undoContractTerms: (id: string, setUpOpId: string, lang: "en" | "zh" = "en") =>
    http<ContractTermsResult>("POST", `/documents/${enc(id)}/terms/undo${lang === "zh" ? "?lang=zh" : ""}`, { body: { set_up_op_id: setUpOpId } }),

  // the buy side (ADR-0013, FEATURE_CAPEX_CONTRACTS): every route needs the owner token; the responses already have the page's shape
  getPurchases: (lang: "en" | "zh" = "en") => http<PurchasesView>("GET", `/purchases${lang === "zh" ? "?lang=zh" : ""}`),
  getPurchase: async (id: string, lang: "en" | "zh" = "en"): Promise<PurchaseRow> =>
    (await http<{ purchase: PurchaseRow }>("GET", `/purchases/${enc(id)}${lang === "zh" ? "?lang=zh" : ""}`)).purchase,
  getCapexContractFixtures: async (): Promise<ContractFixture[]> =>
    (await http<{ contracts: ContractFixture[] }>("GET", "/fixtures/capex-contracts")).contracts,
  evaluateContract: (id: string, timeline: BuyTimeline, estimate: BuyEstimate = {}) =>
    http<BuySideEvaluationView>("POST", `/capex/contracts/${enc(id)}/evaluate`, { body: { timeline, estimate } }),
  commitContract: (id: string, timeline: BuyTimeline, scheduleHash: string, takeEarlyPay: boolean) =>
    http<PurchaseCommitResult>("POST", `/capex/contracts/${enc(id)}/commit`, {
      body: { timeline, schedule_hash: scheduleHash, take_early_pay: takeEarlyPay },
    }),
  getFinanceHealth: (inputs: HealthInputsRequest | null = null) =>
    inputs ? http<FinanceHealthView>("POST", "/finance/health", { body: { inputs } }) : http<FinanceHealthView>("GET", "/finance/health"),
  getEligibility: (inputs: { months_trading?: number | null; amount_fen?: number | null } | null = null) =>
    inputs ? http<EligibilityView>("POST", "/lending/eligibility", { body: { inputs } }) : http<EligibilityView>("GET", "/lending/eligibility"),
  addProductToMenu: (productId: string, amountFen: number | null = null) =>
    http<AddToMenuResult>("POST", `/lending/products/${enc(productId)}/add-to-menu`, { body: amountFen ? { amount_fen: amountFen } : {} }),
  runCapexPlans: (req: CapexPlansRequest) => http<CapexPlansView>("POST", "/capex/plans", { body: req }),

  /** GET /nav/counts: numbers only (deals needing the owner, approvals pending, late invoices). */
  getNavCounts: (lang: "en" | "zh" = "en") => http<NavCounts>("GET", `/nav/counts?lang=${lang}`),
  /** GET /offers/{id}/picture: the offer's cash line as asked and of each reply ready. */
  getOfferPicture: (offerId: string, lang: "en" | "zh" = "en") => http<OfferPictureView>("GET", `/offers/${enc(offerId)}/picture?lang=${lang}`),

  /** GET /customers/{id}/overview: one page's read; the context (`decision`, `path`, `invoice`) only builds the back link. */
  getCustomerOverview: (id: string, lang: "en" | "zh", ctx: CustomerContext = {}) =>
    http<CustomerOverviewView>("GET", `/customers/${enc(id)}/overview?lang=${lang}${contextQuery({ ...ctx, scenario: serverScenario(ctx.scenario) })}`),

  getBuyerInputs: (id: string, lang: "en" | "zh", ctx: CustomerContext = {}) =>
    http<InputSheetView>("GET", `/buyers/${enc(id)}/inputs?lang=${lang}${contextQuery({ ...ctx, scenario: serverScenario(ctx.scenario) })}`),

  saveInput: (id: string | null, body: InputSaveRequest, lang: "en" | "zh") =>
    http<InputSaveResult>("POST", `${id === null ? "/firm/inputs" : `/buyers/${enc(id)}/inputs`}?lang=${lang}`, { body }),

  // set up your books (ADR-0013)
  getSetupStatus: (lang: "en" | "zh") => http<SetupStatus>("GET", `/setup/status?lang=${lang}`, { silent: true }),
  getSetupDocuments: async (startDate: string, lang: "en" | "zh"): Promise<SetupDocument[]> =>
    (await http<{ documents: SetupDocument[] }>("GET", `/setup/documents?lang=${lang}${startDate ? `&start_date=${enc(startDate)}` : ""}`)).documents,
  readSetupDocument: async (body: Record<string, unknown>, lang: "en" | "zh"): Promise<SetupDocument> =>
    (await http<{ document: SetupDocument }>("POST", `/setup/documents?lang=${lang}`, { body, timeoutMs: 60_000 })).document,
  previewSetup: (draft: SetupDraft, lang: "en" | "zh") => http<SetupPreview>("POST", `/setup/preview?lang=${lang}`, { body: { draft } }),
  openBooks: (draft: SetupDraft, password: string, lang: "en" | "zh") =>
    http<SetupOpenResult>("POST", `/setup/open?lang=${lang}`, { body: { draft, password }, timeoutMs: 60_000, silent: true }),

  /** Owner action: close a counterparty's circuit breaker. The server checks X-Owner-Token. */
  resetCircuit: async (counterpartyId: string): Promise<{ status: string; message: string }> => {
    const { result } = await http<{ result: { status: string; message: string } }>("POST", `/circuit/${enc(counterpartyId)}/reset`);
    if (result.status === "REFUSED") throw new ApiError(403, result.message);
    return result;
  },
};
