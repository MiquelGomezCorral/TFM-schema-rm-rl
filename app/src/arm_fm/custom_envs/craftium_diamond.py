"""Register ``Craftium/Diamond-v0``, the sparse wood-stone-iron-diamond task.

The environment class (``craftium_diamond_env.DiamondEnv``) is named by a string entry point, so
Craftium is only imported when the environment is created.
"""

from gymnasium.envs.registration import WrapperSpec, register

# OpenWorld's keys; the Discrete action wrapper adds a leading no-op.
KEYS = [
    "forward",
    "backward",
    "left",
    "right",
    "jump",
    "sneak",
    "dig",
    "place",
    "slot_1",
    "slot_2",
    "slot_3",
    "slot_4",
    "slot_5",
]

register(
    id="Craftium/Diamond-v0",
    entry_point="src.arm_fm.custom_envs.craftium_diamond_env:DiamondEnv",
    additional_wrappers=[
        WrapperSpec(
            name="DiscreteActionWrapper",
            entry_point="craftium.wrappers:DiscreteActionWrapper",
            kwargs={
                "actions": [*KEYS, "mouse x+", "mouse x-", "mouse y+", "mouse y-"],
                "mouse_mov": 0.1,
            },
        )
    ],
    kwargs={
        "obs_width": 320,
        "obs_height": 180,
        "rgb_observations": False,
        "init_frames": 200,
        "game_id": "VoxeLibre",
        "max_steps": 10_000,
        "_minetest_conf": {
            "max_block_generate_distance": 3,
            "hud_scaling": 0.5,
            "fov": 90,
            "console_alpha": 0,
            "smooth_lighting": False,
            "performance_tradeoffs": True,
            "enable_particles": False,
            "enable_clouds": False,  # random cloud positions would change the start frame
        },
    },
)
