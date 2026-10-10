import type { Metadata } from "next";
import { en, type DictKey } from "./dictionary";

/**
 * The browser-tab title of a route, rendered on the server so a hard load, a reload and a bookmark all carry it ("Deals · FLOW 流"; the
 * root layout holds the template). English here: the shell swaps in the owner's language once it is known (`useDocumentMeta` in
 * components/app-shell.tsx), and keeps it when Next rewrites the tab on a client navigation.
 */
export const routeTitle = (key: DictKey): Metadata => ({ title: en[key] });
