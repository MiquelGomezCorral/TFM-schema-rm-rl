"""Register the XLand-MiniGrid id; the env module loads (and boots JAX) only when one is made."""

from gymnasium.envs.registration import register

ENV_ID = "XLand-R4-13x13-v0"

register(id=ENV_ID, entry_point="src.arm_fm.custom_envs.xland_env:XLandEnv")
