"""Replace this workspace's local paths in an evidence folder before it is sealed (the Linux counterpart of the
baseline's tools/scrub_paths.py): the candidate checkout -> <repo-root>, the control checkout -> <control-root>,
the gate output folder -> $OUT, the scratchpad -> $SCRATCH, the home folders -> ~. Byte-wise. Usage: scrub_paths_linux.py <folder>"""
import pathlib
import re
import sys

PATS = (
    (re.compile(rb"/tmp/claude-0/[A-Za-z0-9_.-]+/[0-9a-f-]{36}/scratchpad"), b"$SCRATCH"),
    (re.compile(rb"(?:/root|/home/claude)/flow-gate/cand"), b"<repo-root>"),
    (re.compile(rb"(?:/root|/home/claude)/flow-gate/base"), b"<control-root>"),
    (re.compile(rb"(?:/root|/home/claude)/flow-gate/proto"), b"<prototype-root>"),
    (re.compile(rb"(?:/root|/home/claude)/flow-gate/out"), b"$OUT"),
    (re.compile(rb"<repo-root>"), b"<repo-root>"),
    (re.compile(rb"(?:/root|/home/claude)(?=/)"), b"~"),
)
n = 0
for f in pathlib.Path(sys.argv[1]).rglob("*"):
    if not f.is_file() or f.suffix.lower() in (".png", ".jpg", ".jpeg", ".zip", ".gz", ".webm"):
        continue
    b = o = f.read_bytes()
    for pat, rep in PATS:
        b = pat.sub(rep, b)
    if b != o:
        f.write_bytes(b)
        n += 1
print("files cleaned", n)
