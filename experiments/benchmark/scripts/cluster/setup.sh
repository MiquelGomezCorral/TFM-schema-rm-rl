#!/usr/bin/env bash
# Build the training venv on the tensor cluster (runs there, inside a SLURM job):
#   srun -p docencia -c 8 --mem 16G -t 60 bash ~/tfm/cluster/setup.sh
# Needs uv in ~/.local/bin and the repo clone in ~/tfm/repo (see README.md).
# The venv gets requirements.txt (no MONA, llama-server or Craftium: training does not use them).
set -euo pipefail

repo="$HOME/tfm/repo"
venv="$HOME/tfm/venv"
uv="$HOME/.local/bin/uv"

"$uv" venv --allow-existing --python 3.13 "$venv"
env -C "$repo" "$uv" pip install --python "$venv/bin/python" -r requirements.txt
# requirements.txt lacks Pillow, which app/scripts/test_rl.py imports (RM_RL_env has it, 12.3.0).
"$uv" pip install --python "$venv/bin/python" pillow==12.3.0
"$venv/bin/python" -c "import PIL, torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
