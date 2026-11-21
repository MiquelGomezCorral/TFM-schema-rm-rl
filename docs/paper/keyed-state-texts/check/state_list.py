"""Print a machine's state list (role, owed stages, a shortest way in) to judge texts against.

The list is the view a machine over the prompt bound reaches the tagger as; the bound is set to
zero here so any machine prints it. No model call.

Usage (PYTHONPATH=<worktree>/app): python state_list.py REWARD_MACHINE_TXT
"""

import sys
from pathlib import Path

from src.compiler.rm_format import machine_view
from src.config import Configuration

Configuration.MACHINE_PROMPT_MAX_CHARS = 0
print(machine_view(Path(sys.argv[1]).read_text(encoding="utf-8")))
