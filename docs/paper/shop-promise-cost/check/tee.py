"""Run a check script and keep what it prints: python tee.py OUT.out SCRIPT.py [ARGS...].

The script runs in this process, so it can import only what PYTHONPATH reaches (app/ for src), not a
sibling script; none of the scripts the entry's .out files come from does.
"""

import contextlib
import io
import runpy
import sys
from pathlib import Path

out, script, *args = sys.argv[1:]
sys.argv = [script, *args]
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    runpy.run_path(script, run_name="__main__")
Path(out).write_text(buffer.getvalue(), encoding="utf-8")
print(buffer.getvalue(), end="")
