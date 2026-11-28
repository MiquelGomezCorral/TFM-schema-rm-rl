# Install

Back to the [main page](../README.md).

## 1. The Python environment

FARM runs on Linux or macOS, in one Conda environment with Python 3.13.

```bash
git clone --recurse-submodules https://github.com/MiquelGomezCorral/TFM-schema-rm-rl.git
cd TFM-schema-rm-rl
conda create --name RM_RL_env python=3.13 -y
conda activate RM_RL_env
uv pip install --python "$CONDA_PREFIX/bin/python" --torch-backend auto -r requirements.txt
uv pip install --python "$CONDA_PREFIX/bin/python" -e .
```

`requirements.txt` is the reference for this environment. Training uses pinned versions of
Torch, Stable-Baselines3, Transformers and MiniGrid, so use this one environment for everything.

## 2. MONA

MONA is the tool that builds the automata. The `mona` program must be on your `PATH`.

- **With a package manager.** `setup.sh` installs it this way when it can.
- **From source.** Download it from <https://www.brics.dk/mona/download.html>, unpack it and run:

```bash
./configure --prefix="$HOME/.local"
make
make install
export PATH="$HOME/.local/bin:$PATH"
mona -v
```

You may need your system's build tools first. If MONA is somewhere else, set `MONA_EXECUTABLE`
in `.env`.

## 3. Check the install

Neither command calls a language model:

```bash
mona -v
python app/main.py --help
```

## Optional

### `setup.sh`

The older `setup.sh` sets up the submodules, the project and MONA in a `.venv`. It is enough
to generate RMs. Do not use its `.venv` for training or embeddings.

### Jupyter

```bash
python -m pip install ipykernel
python -m ipykernel install --user --name=RM_RL_env --display-name "Python (RM_RL_env)"
```

### Changing nl2ltl or FL-AT

The two tools live in `dependencies/` as git submodules, checked out at a fixed commit. Before
editing one, switch to its main branch and add the original repository as `upstream`:

```bash
cd dependencies/nl2ltl
git switch main
git pull --ff-only origin main
git remote add upstream https://github.com/IBM/nl2ltl.git

cd ../Flat
git switch master
git pull --ff-only origin master
git remote add upstream https://github.com/Jamidd/Flat.git
```

In both, `origin` is the fork and `upstream` the original project. Commit and push the change
inside the submodule, then go back to this repository and commit the new submodule pointer.
