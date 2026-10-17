import { expect, test, type Locator, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

/**
 * The recording kit of the demo videos (e2e/video): the overlay a viewer sees (caption bar with a step counter, a visible pointer, title
 * cards; added by the spec, not product code), smooth motion, and the `Reel` that runs a list of scenes as numbered chapters, times them
 * and keeps any failure with a screenshot. The scenes are in story.ts (the 5-minute cut) and tour.ts (the full tour); walkthrough.spec.ts orders them into cuts.
 */

const FRAMES = process.env.VIDEO_FRAMES_DIR ?? "";
/** The longest one scene may take (a full-tour chapter runs two to four minutes). */
const SCENE_LIMIT_MS = 8 * 60_000;

/** What a scene gets: the page, an API client, and its cut's pace (every viewing pause is multiplied by it). */
export interface Scene {
  /** A stable id (README, logs). */
  id: string;
  /** The chapter's title, shown in the caption bar and the README. */
  title: string;
  /** The chapter's first caption. */
  caption: string;
  /** What the chapter shows, for the README's chapter table (one plain sentence). */
  about?: string;
  run: (reel: Reel) => Promise<void>;
}

export type Cut = "5min" | "full";

/** One recording: the chapters run so far, their start times and anything that went wrong. */
export class Reel {
  readonly marks: { n: number; id: string; title: string; about?: string; at: number }[] = [];
  readonly problems: { chapter: number; title: string; error: string; screenshot: string }[] = [];
  private readonly t0 = Date.now();
  private current = 0;

  constructor(
    readonly page: Page,
    readonly cut: Cut,
    /** Every viewing pause is multiplied by this (the 5-minute cut reads faster). */
    readonly pace: number,
    readonly scenes: Scene[],
  ) {}

  get seconds(): number {
    return (Date.now() - this.t0) / 1000;
  }

  /** A pause for the viewer, never for correctness. */
  hold(seconds: number): Promise<void> {
    return this.page.waitForTimeout(seconds * this.pace * 1000);
  }

  /** The caption under the current chapter: one short sentence (HTML allowed). */
  async say(text: string): Promise<void> {
    const n = this.current;
    const title = this.scenes[n - 1]?.title ?? "";
    const caption = { step: `${n} / ${this.scenes.length}`, text: `<b>${n} · ${title}</b> — ${text}` };
    await this.page.evaluate((c) => {
      sessionStorage.setItem("vw-caption", JSON.stringify(c));
      // Drawn at once (the overlay's own timer would take up to 200 ms): a key frame taken next shows this caption.
      const step = document.getElementById("vw-step");
      const text = document.getElementById("vw-text");
      if (step) step.textContent = c.step;
      if (text) text.innerHTML = c.text;
    }, caption);
  }

  /** Runs every scene in order; a failure is kept with a screenshot and the next scene runs. */
  async play(): Promise<void> {
    for (const [i, scene] of this.scenes.entries()) {
      this.current = i + 1;
      this.marks.push({ n: i + 1, id: scene.id, title: scene.title, about: scene.about, at: this.seconds });
      console.log(`[reel] ${this.cut} ${i + 1}/${this.scenes.length} ${scene.title} at ${this.seconds.toFixed(1)} s`);
      await this.say(scene.caption);
      try {
        // A scene that hangs (a page that never loads) ends the recording here, with what ran so far kept: never a silent wait to the test's timeout.
        let timer: ReturnType<typeof setTimeout> | undefined;
        const limit = new Promise<"hung">((done) => (timer = setTimeout(() => done("hung"), SCENE_LIMIT_MS)));
        const outcome = await Promise.race([scene.run(this).then(() => "done" as const), limit]);
        clearTimeout(timer);
        if (outcome === "hung") {
          const shot = test.info().outputPath(`problem-${i + 1}-${scene.id}.png`);
          await this.page.screenshot({ path: shot, timeout: 10_000 }).catch(() => undefined);
          this.problems.push({ chapter: i + 1, title: scene.title, error: `did not finish within ${SCENE_LIMIT_MS / 60_000} minutes; the recording stops here`, screenshot: shot });
          console.log(`[reel] ${scene.title} did not finish within ${SCENE_LIMIT_MS / 60_000} minutes: stopping`);
          return;
        }
      } catch (e) {
        const shot = test.info().outputPath(`problem-${i + 1}-${scene.id}.png`);
        await this.page.screenshot({ path: shot }).catch(() => undefined);
        this.problems.push({ chapter: i + 1, title: scene.title, error: String(e instanceof Error ? e.message : e).split("\n").slice(0, 6).join(" "), screenshot: shot });
        console.log(`[reel] problem in ${scene.title}: ${this.problems[this.problems.length - 1].error}`);
      }
    }
  }

  /** chapters.json in the test's output folder: what the recorder turns into the README. */
  write(name: string): void {
    writeFileSync(test.info().outputPath("chapters.json"), JSON.stringify({ cut: this.cut, name, total_seconds: this.seconds, chapters: this.marks, problems: this.problems }, null, 2));
  }

  /** A file in the test's output folder (a download kept for a check). */
  outputPath(name: string): string {
    return test.info().outputPath(name);
  }

  /** A key frame for the README and the report (VIDEO_FRAMES_DIR/<cut>-<name>.png). */
  async frame(name: string): Promise<void> {
    if (!FRAMES) return;
    mkdirSync(FRAMES, { recursive: true });
    await this.page.screenshot({ path: join(FRAMES, `${this.cut}-${name}.png`) });
  }
}

// ---------------------------------------------------------------- the overlay

/** Installed before every page: the caption bar, the step counter, a visible pointer, and the dev-build badge hidden. Tours stay off. */
export async function installOverlay(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("tl-tours-off", "1");
    } catch {
      /* storage unavailable: the automated browser gets no autoplay tour anyway */
    }
    const css = `
      nextjs-portal, [data-nextjs-toast], #__next-build-watcher { display: none !important; }
      #vw-bar { position: fixed; left: 50%; bottom: 22px; transform: translateX(-50%); z-index: 2147483646; pointer-events: none;
        display: flex; align-items: center; gap: 16px; max-width: min(1500px, calc(100vw - 80px)); padding: 14px 22px 14px 14px;
        border-radius: 18px; background: rgba(17, 22, 28, 0.88); color: #fff; box-shadow: 0 12px 40px rgba(0,0,0,.28);
        font: 500 21px/1.35 "Plus Jakarta Sans Variable", "Segoe UI", system-ui, sans-serif; letter-spacing: -0.005em;
        backdrop-filter: blur(6px); transition: opacity .35s ease; }
      #vw-bar[data-empty="1"] { opacity: 0; }
      #vw-step { flex: none; display: grid; place-items: center; min-width: 64px; height: 44px; padding: 0 12px; border-radius: 12px;
        background: #7c4dff; font-weight: 800; font-size: 18px; font-variant-numeric: tabular-nums; }
      #vw-text b { font-weight: 800; }
      #vw-pointer { position: fixed; left: 0; top: 0; z-index: 2147483647; pointer-events: none; width: 22px; height: 22px; margin: -11px 0 0 -11px;
        border-radius: 50%; background: rgba(124, 77, 255, .35); border: 2px solid rgba(124, 77, 255, .95); box-shadow: 0 0 0 4px rgba(255,255,255,.55);
        transition: transform .28s cubic-bezier(.2,.7,.2,1), opacity .3s; opacity: 0; }
      #vw-pointer.down { background: rgba(124, 77, 255, .75); }
      #vw-card { position: fixed; inset: 0; z-index: 2147483645; pointer-events: none; display: grid; place-items: center;
        background: radial-gradient(circle at 30% 20%, #2b1d5c, #0e1116 70%); color: #fff; text-align: center;
        font-family: "Plus Jakarta Sans Variable", "Segoe UI", system-ui, sans-serif; transition: opacity .6s ease; }
      #vw-card h1 { font-size: 92px; font-weight: 800; letter-spacing: -0.03em; margin: 0 0 18px; }
      #vw-card p { font-size: 30px; font-weight: 500; opacity: .9; margin: 0 auto; max-width: 1300px; line-height: 1.4; }
      #vw-card small { display: block; margin-top: 34px; font-size: 20px; opacity: .6; }`;
    const ensure = () => {
      if (!document.body) return;
      if (!document.getElementById("vw-style")) {
        const style = document.createElement("style");
        style.id = "vw-style";
        style.textContent = css;
        document.head.appendChild(style);
      }
      let bar = document.getElementById("vw-bar");
      if (!bar) {
        bar = document.createElement("div");
        bar.id = "vw-bar";
        bar.setAttribute("aria-hidden", "true");
        bar.innerHTML = '<span id="vw-step"></span><span id="vw-text"></span>';
        document.body.appendChild(bar);
      }
      let pointer = document.getElementById("vw-pointer");
      if (!pointer) {
        pointer = document.createElement("div");
        pointer.id = "vw-pointer";
        document.body.appendChild(pointer);
        const at = sessionStorage.getItem("vw-pointer");
        if (at) {
          const [x, y] = at.split(",").map(Number);
          pointer.style.transition = "none";
          pointer.style.transform = `translate(${x}px, ${y}px)`;
          pointer.style.opacity = "1";
          requestAnimationFrame(() => pointer && (pointer.style.transition = ""));
        }
      }
      let caption: { step: string; text: string } = { step: "", text: "" };
      try {
        caption = JSON.parse(sessionStorage.getItem("vw-caption") ?? '{"step":"","text":""}');
      } catch {
        /* keep the empty caption */
      }
      const step = document.getElementById("vw-step");
      const text = document.getElementById("vw-text");
      if (step && step.textContent !== caption.step) step.textContent = caption.step;
      if (text && text.innerHTML !== caption.text) text.innerHTML = caption.text;
      bar.dataset.empty = caption.text ? "0" : "1";
      const card = sessionStorage.getItem("vw-card");
      let shown = document.getElementById("vw-card");
      if (card && !shown) {
        shown = document.createElement("div");
        shown.id = "vw-card";
        shown.innerHTML = card;
        document.body.appendChild(shown);
      } else if (!card && shown) shown.remove();
    };
    window.addEventListener("mousemove", (e) => {
      const p = document.getElementById("vw-pointer");
      if (!p) return;
      p.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      p.style.opacity = "1";
      try {
        sessionStorage.setItem("vw-pointer", `${e.clientX},${e.clientY}`);
      } catch {
        /* the pointer starts hidden on the next page */
      }
    });
    window.addEventListener("mousedown", () => document.getElementById("vw-pointer")?.classList.add("down"));
    window.addEventListener("mouseup", () => document.getElementById("vw-pointer")?.classList.remove("down"));
    document.addEventListener("DOMContentLoaded", ensure);
    setInterval(ensure, 200);
  });
}


/** A full-screen title card (the opening and the end card), or none. */
export async function card(page: Page, html: string | null): Promise<void> {
  await page.evaluate((h) => {
    if (h) sessionStorage.setItem("vw-card", h);
    else sessionStorage.removeItem("vw-card");
    const shown = document.getElementById("vw-card");
    if (!h && shown) {
      shown.style.opacity = "0";
      setTimeout(() => shown.remove(), 650);
    }
  }, html);
  if (html) await page.locator("#vw-card").waitFor();
}

// ---------------------------------------------------------------- motion

/** Scrolls the page smoothly so `target` sits near the top (or the centre) of the window. */
export async function glide(page: Page, target: Locator, where: "top" | "center" = "top", ms = 1100): Promise<void> {
  await target.waitFor();
  const y = await target.evaluate((el, w) => {
    const r = el.getBoundingClientRect();
    return w === "center" ? r.top + window.scrollY - Math.max(0, (window.innerHeight - r.height) / 2) : r.top + window.scrollY - 96;
  }, where);
  await scrollTo(page, y, ms);
}

export async function scrollTo(page: Page, y: number, ms = 1100): Promise<void> {
  await page.evaluate(
    ([to, duration]) =>
      new Promise<void>((done) => {
        const el = document.scrollingElement ?? document.documentElement;
        const max = el.scrollHeight - window.innerHeight;
        const from = window.scrollY;
        const dist = Math.min(Math.max(0, to), Math.max(0, max)) - from;
        const start = performance.now();
        const step = (now: number) => {
          const k = Math.min(1, (now - start) / duration);
          const ease = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
          window.scrollTo({ top: from + dist * ease, behavior: "instant" });
          if (k < 1) requestAnimationFrame(step);
          else done();
        };
        requestAnimationFrame(step);
      }),
    [y, ms] as const,
  );
}

/** Moves the visible pointer onto an element (a hover the viewer can see). */
export async function point(page: Page, target: Locator): Promise<void> {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) return;
  await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height / 2, 24), { steps: 12 });
}

/** Clicks with the pointer travelling there first, so the viewer sees what is pressed. */
export async function press(page: Page, target: Locator): Promise<void> {
  await target.waitFor();
  // The pointer's trip is for the viewer: a page that re-renders under it (the element replaced) must not fail the click.
  await point(page, target).catch(() => undefined);
  await target.click();
}

/** Types into a field a character at a time (slowMo paces each key), after clearing it. */
export async function type(page: Page, field: Locator, text: string): Promise<void> {
  await point(page, field);
  await field.click();
  await field.fill("");
  await field.pressSequentially(text);
}

const RAIL: Record<string, string> = {
  Home: "/",
  Deals: "/deals",
  "Attach deals": "/documents",
  "Cash & funding": "/cash",
  Sandbox: "/whatif",
  Capex: "/capex",
  Receivables: "/receivables",
  Activity: "/activity",
};

/** A section of the app from the rail, as the owner gets there. */
export async function go(page: Page, name: string, path: RegExp): Promise<void> {
  // The link's name can carry its badge ("Receivables, 1 overdue"): matched on its start, the visible one.
  const link = page
    .getByTestId("nav-rail")
    .getByRole("link", { name: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`) })
    .filter({ visible: true })
    .first();
  // A page without the rail (the landing page, a dry run's first page) is left by its address.
  if (await link.waitFor({ timeout: 3000 }).then(() => true, () => false)) await press(page, link);
  else await page.goto(RAIL[name] ?? "/");
  await page.waitForURL(path);
  // Off the rail, so its flyout folds away again.
  await page.mouse.move(960, 420, { steps: 10 });
}

// ---------------------------------------------------------------- the app around the scenes

const API = process.env.VIDEO_API_URL ?? "http://localhost:8090";
/** The local demo build's published owner token (scripts/demo.mjs runs the API with DEMO_MODE=1). */
export const DEMO_TOKEN = "demo-owner-token";

/** The API, as the owner, from the test (the books a take starts on, the synthetic bank event). */
export async function ownerPost(page: Page, route: string): Promise<unknown> {
  const res = await page.request.post(`${API}${route}`, { headers: { "X-Owner-Token": DEMO_TOKEN }, data: {} });
  if (!res.ok()) throw new Error(`POST ${route}: ${res.status()} ${(await res.text()).slice(0, 300)}`);
  return res.json();
}

/**
 * A new take inside the same recording: a title card goes up, the books are replaced (`POST /demo/reset?scenario=`), the browser's
 * per-session reads are dropped (the sign-in and the overlay stay), Home is opened, and the card comes down. One cut stays one file.
 */
export async function take(reel: Reel, scenario: "golden_sme" | "blank" | "busy", html: string, seconds = 4): Promise<void> {
  const { page } = reel;
  await card(page, html);
  await ownerPost(page, `/demo/reset?scenario=${scenario}`);
  await page.evaluate(() => {
    for (const k of Object.keys(sessionStorage)) if (!k.startsWith("vw-") && k !== "tl-owner-auth" && k !== "tl-welcomed") sessionStorage.removeItem(k);
    localStorage.removeItem("tl-setup-draft");
  });
  await page.goto("/");
  await page.locator("main").first().waitFor();
  await page.waitForTimeout(seconds * 1000);
  await card(page, null);
}

/**
 * The header's Business / Demo switch, as the owner presses it. The switch opens its shell's start page (Demo: the story page, Business:
 * Home); `back` returns to the page the owner was on.
 */
export async function setMode(page: Page, mode: "business" | "demo", back = false): Promise<void> {
  const radio = page.locator(`input[name="mode"][value="${mode}"]`).first();
  const stored = () => page.evaluate(() => (JSON.parse(localStorage.getItem("tl-mode") ?? '{"mode":"business"}') as { mode: string }).mode);
  if ((await stored()) === mode) return;
  const from = page.url();
  await point(page, radio);
  await radio.click();
  await expect.poll(stored).toBe(mode);
  await page.waitForLoadState();
  if (back && page.url() !== from) await page.goto(from);
}

/** The app's language, from the account menu. */
export async function setLang(page: Page, lang: "en" | "zh"): Promise<void> {
  const menu = page.getByTestId("account-menu");
  if (!(await menu.evaluate((el) => (el as HTMLDetailsElement).open))) await press(page, menu.locator("> summary"));
  const radio = menu.locator(`input[name="lang"][value="${lang}"]`);
  await point(page, radio);
  await radio.check();
  await expect(page.locator("html")).toHaveAttribute("lang", lang === "zh" ? /zh/ : /en/);
  await page.keyboard.press("Escape");
}

/** The simulated clock, moved on the Demo page's Operator tools as the owner does it; waits for the server's new day. */
export async function advanceClock(page: Page, days: number, toDay: number): Promise<void> {
  if (!new URL(page.url()).pathname.startsWith("/demo")) await page.goto("/demo");
  const tools = page.getByTestId("demo-operator-tools");
  await tools.waitFor();
  if (!(await tools.evaluate((el) => (el as HTMLDetailsElement).open))) await press(page, tools.locator("> summary"));
  await glide(page, page.getByTestId("demo-tools-clock"), "center", 600);
  const field = page.getByTestId("home-days");
  await point(page, field);
  await field.fill(String(days));
  await press(page, page.getByTestId("home-advance"));
  await expect(page.getByTestId("home-day")).toContainText(`Day ${toDay}`);
}
