"""Craftium diamond task: OpenWorld cut down to a sparse wood-stone-iron-diamond chain.

``DiamondEnv`` runs the Lua mod in ``craftium_diamond/``. The mod grants the next pickaxe at each
milestone and writes an atomic JSON snapshot of its cumulative state every engine step. This class
reads that snapshot after every ``reset()``/``step()``, exposes it as ``inventory`` and
``milestones`` to the Reward Machine labeling functions, and pays the only reward: 1.0 with
termination on the step whose accepted snapshot first shows the diamond milestone. Craftium's own
reward flag is ignored (its client reads reward and termination without a lock against the engine
thread, so a frame can carry one without the other); death still terminates natively with reward 0.
Every reset restarts the engine on a pristine copy of the world. An engine that dies while starting
is restarted; one that dies mid-episode truncates the episode (``info["engine_crashed"]``).
"""

import json
import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from types import MappingProxyType
from typing import Any

import craftium
from craftium.craftium_env import CraftiumEnv
from gymnasium import Env
from gymnasium.spaces import Box

ENV_FILES = Path(__file__).parent / "craftium_diamond"
SNAPSHOT_NAME = "craftium_state.json"
# The engine finishes a step slightly after the client sends its frame, so the snapshot may lag
# one step; the reader waits this long for the step counter to advance before calling it stale.
SNAPSHOT_TIMEOUT_SECONDS = 5.0
SNAPSHOT_POLL_SECONDS = 0.0005
ENGINE_EXIT_SECONDS = 30.0
ENGINE_START_ATTEMPTS = 3
RESOURCES = ("wood", "stone", "iron", "diamond")


class CraftiumBridgeError(RuntimeError):
    """The mod's state snapshot is missing, stale, from another episode or inconsistent."""


class DiamondEnv(CraftiumEnv):
    """Craftium environment with a fixed world, a diamond-only reward and a state bridge.

    Args:
        max_steps (int): Agent steps before the episode is truncated (OpenWorld uses 10,000).
        **kwargs: Other ``CraftiumEnv`` arguments (``frameskip``, ``run_dir_prefix``...).
            ``minetest_conf={"craftium_debug_route": "wood@300,stone@300,iron@330,diamond@360"}``
            makes the mod grant a milestone at that engine step (counted from the player's join;
            about 206 pass before the first observation) as if the agent had dug it, for scripted
            routes. Not supported:
            ``soft_reset`` (every reset restarts the engine) and ``sync_mode`` (forced on, so the
            mod's step counter must advance after every agent step; no exact engine-to-agent step
            ratio is promised); passing either raises TypeError.
    """

    def __init__(self, max_steps: int = 10_000, **kwargs: Any) -> None:
        self._episode = 0
        self._engine_frames = 0
        self._engine_crashes = 0
        self._closed = False
        self._clear_state()
        # Craftium would otherwise create the engine's run dir in the current directory.
        kwargs.setdefault("run_dir_prefix", tempfile.gettempdir())
        # Craftium would draw the engine's port from the global ``random``, which a seeded run
        # shares with every other run of the same seed: their engines would collide on it. The
        # port stays the same for every engine of this env: the engine's sync semaphores are named
        # after it, and its client only finds them once an engine on that port has created them.
        kwargs.setdefault("mt_port", _free_udp_port())

        with tempfile.TemporaryDirectory(prefix="craftium-diamond-env-") as env_dir:
            _assemble_env_dir(Path(env_dir))
            # The engine copies env_dir into its run dir, so the assembly is not needed afterwards.
            super().__init__(
                env_dir=env_dir,
                max_timesteps=max_steps,
                sync_mode=True,
                soft_reset=False,
                **kwargs,
            )

        # The engine files and the listener exist now: any failure below must release them.
        try:
            # CraftiumEnv declares (width, height, ...) but returns (height, width, ...) frames.
            height_first = (self.observation_space.shape[1], self.observation_space.shape[0])
            self.observation_space = Box(
                0, 255, (*height_first, *self.observation_space.shape[2:]), dtype="uint8"
            )

            run_dir = Path(self.mt.run_dir)
            self._world = run_dir / "worlds" / "world"
            self._pristine_world = run_dir / "pristine-world"
            shutil.copytree(self._world, self._pristine_world)
        except BaseException:
            self.close()
            raise

    @property
    def inventory(self) -> Mapping[str, int]:
        """Dug nodes per resource this episode: ``{"wood", "stone", "iron", "diamond"}`` -> int."""
        return self._inventory

    @property
    def milestones(self) -> Mapping[str, bool]:
        """Milestones reached this episode, in order: wood, stone, iron, diamond.

        A flag only turns on during an episode; ``reset()`` clears all of them.
        """
        return self._milestones

    @property
    def engine_step(self) -> int:
        """The mod's step counter at the latest snapshot; it starts when the player joins."""
        return self._engine_step

    @property
    def engine_frames(self) -> int:
        """Engine steps simulated over all episodes, counting each episode's start-up frames."""
        return self._engine_frames

    @property
    def engine_crashes(self) -> int:
        """Episodes truncated because their engine died mid-episode; start-up deaths not counted."""
        return self._engine_crashes

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        """Restart the engine on the pristine world and return the first observation.

        ``seed`` only seeds Gymnasium's RNG: the map comes from the pristine world. An engine that
        dies while starting is restarted; the error is raised after ``ENGINE_START_ATTEMPTS`` tries.
        """
        Env.reset(self, seed=seed)
        for _ in range(ENGINE_START_ATTEMPTS - 1):  # the last attempt below raises its error
            try:
                return self._start_episode(options)
            except ConnectionError as error:
                print(f"Craftium engine died while starting ({error}); restarting it", flush=True)
        return self._start_episode(options)

    def _start_episode(self, options: dict | None):
        self._stop_engine()
        shutil.rmtree(self._world)
        shutil.copytree(self._pristine_world, self._world)

        self._episode += 1
        self._clear_state()
        self.mt.overwrite_config({"craftium_episode": self._episode})
        with self._engine_io():
            observation, info = super().reset(options=options)
            self._read_snapshot()
        return observation, info

    def step(self, action):
        try:
            with self._engine_io():
                observation, _native_reward, terminated, truncated, info = super().step(action)
                self._read_snapshot()
        except ConnectionError as error:
            return self._truncate_after_engine_crash(error)
        if self._milestones["diamond"] and not self._diamond_paid:
            self._diamond_paid = True
            return observation, 1.0, True, truncated, info
        return observation, 0.0, terminated, truncated, info

    def _truncate_after_engine_crash(self, error: ConnectionError):
        """End the episode of an engine that died mid-episode; ``reset()`` starts a new one.

        The Luanti engine now and then dies on its own (the wave-3 regression lost its eval engine
        mid-episode twice), and a long run restarts it thousands of times. The episode is
        truncated, not terminated, so a learner reads the crash as a time limit and neither as a
        death nor as a goal.
        """
        self._engine_crashes += 1
        print(
            f"Craftium engine died at engine step {self._engine_step} ({error}); episode truncated",
            flush=True,
        )
        return self.last_observation, 0.0, False, True, {"engine_crashed": True}

    @contextmanager
    def _engine_io(self) -> Iterator[None]:
        """Keep ``mt_chann.connfd`` truthful when an engine read or write fails.

        The extension's receive closes the fd itself only on end of stream ("Connection closed by
        peer"); its other failures leave it open. Either way the handle must not outlive the
        connection: an integer left behind would be reused by the next file the process opens, and
        ``_stop_engine`` would write the kill message into it and close it.
        """
        try:
            yield
        except ConnectionError as error:
            if "Connection closed by peer" not in str(error):
                with suppress(OSError):
                    self.mt_chann.close_conn()
            self.mt_chann.connfd = None
            raise

    def _clear_state(self) -> None:
        self._engine_step = 0
        self._diamond_paid = False
        self._inventory: Mapping[str, int] = MappingProxyType(dict.fromkeys(RESOURCES, 0))
        self._milestones: Mapping[str, bool] = MappingProxyType(dict.fromkeys(RESOURCES, False))

    def close(self, clear: bool = True) -> None:
        """Stop the engine, close its listener and remove the run dir; safe to call twice.

        The listener close and the run dir removal run even if stopping the engine raises.
        """
        if self._closed:
            return
        self._closed = True
        with ExitStack() as cleanup:
            cleanup.callback(super().close, clear)
            cleanup.callback(self.mt_chann.close)
            self._stop_engine()

    def _stop_engine(self) -> None:
        """Reap the engine process and close its pipes and connection, connected or not.

        A connected engine gets the kill message and ``ENGINE_EXIT_SECONDS`` to exit and save; an
        engine that never connected (handshake failed or timed out) is terminated at once. Either
        way a process that is still alive afterwards is killed. An engine that already died
        (``send_kill`` or closing the connection fails with ``OSError``) is simply reaped.
        """
        # ``connfd`` is cleared by ``_engine_io`` when a read or write fails, so an open handle
        # here is a live connection (or a peer that died silently, which the OSError guards cover).
        connected = self.mt_chann.is_open()
        if connected:
            with suppress(OSError):
                self.mt_chann.send_kill()
            with suppress(OSError):
                self.mt_chann.close_conn()
            self.mt_chann.connfd = None
        self.mt.close_pipes()

        process = self.mt.proc
        if process is None:
            return
        if not connected and process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=ENGINE_EXIT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _read_snapshot(self) -> None:
        """Load the mod's snapshot, waiting for its step counter to advance.

        Raises:
            ConnectionError: If the engine exited before it wrote the awaited snapshot.
            CraftiumBridgeError: If no snapshot with an advanced step counter appears in time,
                it belongs to another episode, is unreadable, or a cumulative value went down.
        """
        path = self._world / SNAPSHOT_NAME
        deadline = time.monotonic() + SNAPSHOT_TIMEOUT_SECONDS
        while True:
            snapshot = _load_snapshot(path)
            if snapshot is not None:
                if snapshot["episode"] != self._episode:
                    raise CraftiumBridgeError(
                        f"Snapshot is from episode {int(snapshot['episode'])}, "
                        f"expected {self._episode}"
                    )
                if snapshot["step"] > self._engine_step:
                    break
            if time.monotonic() >= deadline:
                if self.mt.proc.poll() is not None:
                    raise ConnectionError("Craftium engine exited before it wrote its snapshot")
                state = "missing" if snapshot is None else f"stale at step {int(snapshot['step'])}"
                raise CraftiumBridgeError(
                    f"Snapshot {path} is {state}: the step counter did not pass "
                    f"{self._engine_step} within {SNAPSHOT_TIMEOUT_SECONDS} s"
                )
            time.sleep(SNAPSHOT_POLL_SECONDS)

        inventory, milestones = snapshot["inventory"], snapshot["milestones"]
        if any(inventory[name] < self._inventory[name] for name in RESOURCES) or any(
            self._milestones[name] and not milestones[name] for name in RESOURCES
        ):
            raise CraftiumBridgeError("Snapshot went backwards: cumulative state must not shrink")

        self._engine_frames += int(snapshot["step"]) - self._engine_step
        self._engine_step = int(snapshot["step"])
        self._inventory = MappingProxyType({name: int(inventory[name]) for name in RESOURCES})
        self._milestones = MappingProxyType({name: bool(milestones[name]) for name in RESOURCES})


def _free_udp_port() -> int:
    """A UDP port on localhost that no socket holds right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    """Parse the snapshot file; ``None`` while it does not exist yet."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except ValueError as error:
        raise CraftiumBridgeError(f"Unreadable snapshot {path}: {error}") from error


def _assemble_env_dir(target: Path) -> None:
    """Build the engine's env dir: our mod and world file on Craftium's pre-generated world."""
    stock = Path(craftium.__file__).parent / "craftium-envs" / "voxel-libre2"
    (target / "games").symlink_to(stock / "games")
    shutil.copytree(stock / "worlds", target / "worlds")
    shutil.copy(ENV_FILES / "worlds" / "world" / "world.mt", target / "worlds" / "world")
    (target / "mods").mkdir()
    (target / "mods" / "craftium_diamond").symlink_to(
        ENV_FILES / "mods" / "craftium_diamond", target_is_directory=True
    )
