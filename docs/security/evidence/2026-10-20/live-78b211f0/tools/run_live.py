"""Run a certification harness of the frozen build in live mode, with the model key taken from the main checkout's .env,
without showing it.

The environment is fixed first and the loader only fills names that are unset, so the books stay in memory, the demo
credentials stay the published ones, and no database URL can be derived from the .env (it would name the real project).
The loader never prints a value; this script prints only whether each key is present.

Usage (from the frozen checkout's services/api):  python run_live.py <path to .env> <harness script> [harness args...]
"""

import os
import runpy
import sys
from pathlib import Path

env_path, script, *args = sys.argv[1:]
FIXED = {"DATABASE_URL": "memory", "DEMO_MODE": "1", "LLM_REDACT": "1", "LLM_LIVE_RAW": "0", "PYTHONUTF8": "1",
         "OWNER_TOKEN": "demo-owner-token", "AGENT_KEY": "demo-agent-key", "BANK_FEED_KEY": "demo-bank-feed-key",
         "COUNTERPARTY_KEYS": "BUYER-1=demo-buyer-1-key,BUYER-2=demo-buyer-2-key", "SUPABASE_DB_URL": ""}
os.environ.update(FIXED)
os.environ.pop("TERMSLEDGER_NO_DOTENV", None)
sys.path.insert(0, os.getcwd())
from app.config import load_dotenv  # noqa: E402

load_dotenv(Path(env_path))
for k, v in FIXED.items():
    assert os.environ.get(k) == v, f"{k} changed after loading the .env"
print(f"[run_live] deepseek key present: {bool(os.environ.get('DEEPSEEK_API_KEY'))}; "
      f"anthropic key present: {bool(os.environ.get('ANTHROPIC_API_KEY'))}; database: {os.environ['DATABASE_URL']}", flush=True)
if not os.environ.get("DEEPSEEK_API_KEY"):
    sys.exit("no DEEPSEEK_API_KEY in that .env")
os.environ["TERMSLEDGER_NO_DOTENV"] = "1"  # nothing else may load another .env from here on
if script == "-m":  # a module: python run_live.py <.env> -m package.module [args...]
    module, *rest = args
    sys.argv = [module, *rest]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
else:
    sys.argv = [script, *args]
    runpy.run_path(script, run_name="__main__")
