import os, sys, json, traceback
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.setup import SetupDraft, build_books
d = draft(); d["business"]["cash"] = "9" * 5_000_000
try:
    build_books(SetupDraft.model_validate(d))
except BaseException as e:
    traceback.print_exc(limit=3)
from app.main import app
print(len(app.routes), [ (type(r).__name__, getattr(r,'path',None), getattr(r,'methods',None)) for r in app.routes][:12])
