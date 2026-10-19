"""Replace this machine's local paths in an evidence folder before it is sealed: the scratchpad -> $SCRATCH, the repository
parent -> <repo-root>, the home folder -> ~. Byte-wise, so files in any encoding are handled. Usage: scrub_paths.py <folder>"""
import pathlib
import re
import sys

SEP = rb"[\\/]+"
SCR = re.compile(rb"(?:[A-Za-z]:|/[a-z])?" + SEP + rb"Users" + SEP + rb"ian" + SEP + rb"AppData" + SEP + rb"Local" + SEP + rb"Temp" + SEP
                 + rb"claude" + SEP + rb"[A-Za-z0-9_.-]+" + SEP + rb"[0-9a-f-]{36}" + SEP + rb"scratchpad", re.I)
REPO = re.compile(rb"(?:[A-Za-z]:|/[a-z])?" + SEP + rb"Users" + SEP + rb"ian" + SEP + rb"Documents" + SEP + rb"Projects" + SEP + rb"smu2sz", re.I)
HOME = re.compile(rb"(?:[A-Za-z]:|/[a-z])?" + SEP + rb"Users" + SEP + rb"ian(?=[\\/])", re.I)
SLUG = re.compile(rb"C--Users-ian-Documents-Projects-smu2sz")

n = 0
for f in pathlib.Path(sys.argv[1]).rglob("*"):
    if not f.is_file() or f.suffix.lower() in (".png", ".jpg", ".jpeg", ".zip", ".gz"):
        continue
    b = f.read_bytes()
    o = b
    for pat, rep in ((SCR, b"$SCRATCH"), (REPO, b"<repo-root>"), (HOME, b"~"), (SLUG, b"<project-slug>")):
        b = pat.sub(rep, b)
    if b != o:
        f.write_bytes(b)
        n += 1
print("files cleaned", n)
