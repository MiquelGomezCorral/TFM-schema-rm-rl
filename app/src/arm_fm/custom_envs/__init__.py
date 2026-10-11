"""Custom Gymnasium environments; each module here registers its ids when imported."""

# Each environment module adds its own `from . import <module>` line here. A module only calls
# `gymnasium.register` with a string `entry_point` and must not import `src.arm_fm` internals
# at module level, because `src.arm_fm` imports this package first.
