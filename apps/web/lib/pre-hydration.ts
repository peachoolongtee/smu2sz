/**
 * Runs in <head> before the first paint (app/layout.tsx). The server renders the Business shell in English (the one snapshot every
 * visitor shares, so hydration never mismatches); an owner who chose Demo mode or Chinese would see that for a moment before the
 * stores read localStorage. This script reads the same two keys (`tl-lang`, `tl-mode`, written by lib/i18n.ts and lib/mode.ts),
 * sets `lang` and `data-mode` on <html> at once (and `data-sidebar="collapsed"` from `tl-sidebar`, lib/use-sidebar.ts, so a collapsed sidebar is laid out from the first paint), and marks the page `data-pending` when the first paint would show the wrong shell or
 * language: globals.css keeps the body invisible until the shell has hydrated and clears the mark (`components/app-shell.tsx`),
 * and the script itself reveals it after 2 s should hydration never finish. The business routes below mirror `BUSINESS_ROUTES` in lib/mode.ts.
 */
export const PRE_HYDRATION = `(function(){try{
var d=document.documentElement;
var l=JSON.parse(localStorage.getItem("tl-lang")||"{}").lang;
var m=JSON.parse(localStorage.getItem("tl-mode")||"{}").mode;
var biz=["/","/deals","/cash","/receivables","/approvals","/activity","/limits","/whatif","/capex"].indexOf(location.pathname.replace(/(.)\\/$/,"$1"))>-1||location.pathname.indexOf("/decisions/")===0;
d.dataset.mode=m==="demo"?"demo":"business";
if(JSON.parse(localStorage.getItem("tl-sidebar")||"{}").collapsed===true)d.dataset.sidebar="collapsed";
if(l==="zh")d.lang="zh-CN";
if(l==="zh"||m==="demo"&&(biz||location.pathname==="/chat")){d.dataset.pending="";setTimeout(function(){d.removeAttribute("data-pending")},2000);}
}catch(e){}})();`;
