"""BabyAI level for chosen missions: two 8x8 rooms, one door, four fixed objects.

``gym.make("BabyAI-ChosenMission-v0", mission=...)`` selects one of three missions. The
given string stays the mission text; BabyAI's own surface form is not used. Missions 1 and 2
have a native verifier. Mission 3 gets an instruction that never verifies, so only a Reward
Machine can judge it (config ``success: rm``).

Register with a string entry point and import nothing from ``src.arm_fm``: the package
imports ``custom_envs`` first, so a module-level import back would be circular.
"""

from gymnasium.envs.registration import register
from minigrid.envs.babyai.core.roomgrid_level import RoomGridLevel
from minigrid.envs.babyai.core.verifier import (
    ActionInstr,
    BeforeInstr,
    ObjDesc,
    OpenInstr,
    PickupInstr,
    PutNextInstr,
    pos_next_to,
)

PUT_BALL_NEXT_TO_KEY = "put the yellow ball next to the red key"
OPEN_DOOR_THEN_PICK_UP_BOX = "open the green door, then pick up the blue box"
MOVE_BOX_TO_CORNER_THEN_PUT_BALL = (
    "move the purple box to a corner, then put the yellow ball next to the red key"
)
MISSIONS = (PUT_BALL_NEXT_TO_KEY, OPEN_DOOR_THEN_PICK_UP_BOX, MOVE_BOX_TO_CORNER_THEN_PUT_BALL)

# (kind, color) in placement order: yellow ball, red key, blue box, purple box.
OBJECTS = (("ball", "yellow"), ("key", "red"), ("box", "blue"), ("box", "purple"))
ROOM_COUNT = 2


class JudgedByRewardMachine(ActionInstr):
    """Instruction that never verifies: the Reward Machine, not BabyAI, judges the mission."""

    def __init__(self, mission: str) -> None:
        super().__init__()
        self.mission = mission

    def surface(self, _env) -> str:
        return self.mission

    def verify_action(self, _action) -> str:
        return "continue"


class ChosenMission(RoomGridLevel):
    """One row of two rooms joined by a closed, unlocked green door.

    The yellow ball, red key, blue box and purple box are placed at random in either room and
    the agent starts in a random room. Layouts that already satisfy the mission, or that leave
    an object unreachable, are sampled again. In mission 2 the blue box is always in the
    room the agent does not start in, so the door must be opened first.
    """

    def __init__(self, mission: str = PUT_BALL_NEXT_TO_KEY, max_steps: int = 400, **kwargs) -> None:
        if mission not in MISSIONS:
            raise ValueError(f"Unknown mission {mission!r}; use one of {', '.join(MISSIONS)}")
        self.mission_text = mission
        super().__init__(
            room_size=8, num_rows=1, num_cols=ROOM_COUNT, max_steps=max_steps, **kwargs
        )

    def _gen_grid(self, width, height) -> None:
        super()._gen_grid(width, height)
        # RoomGridLevel replaces the mission with the instruction's surface form.
        self.mission = self.mission_text

    def gen_mission(self) -> None:
        self.add_door(0, 0, door_idx=0, color="green", locked=False)
        agent_room = self._rand_int(0, ROOM_COUNT)
        while True:
            objects = self._place_objects(agent_room)
            self.place_agent(agent_room, 0)
            if self.check_objs_reachable(raise_exc=False) and not self._starts_solved(objects):
                break
            self._remove_objects(objects)
        self.instrs = self._instruction()

    def _place_objects(self, agent_room: int) -> list:
        objects = []
        for kind, color in OBJECTS:
            room = self._rand_int(0, ROOM_COUNT)
            if self.mission_text == OPEN_DOOR_THEN_PICK_UP_BOX and color == "blue":
                room = ROOM_COUNT - 1 - agent_room
            objects.append(self.add_object(room, 0, kind, color)[0])
        return objects

    def _remove_objects(self, objects: list) -> None:
        for obj in objects:
            self.grid.set(*obj.cur_pos, None)
        for room in range(ROOM_COUNT):
            self.get_room(room, 0).objs.clear()

    def _starts_solved(self, objects: list) -> bool:
        ball, key, _, purple_box = objects
        ball_next_to_key = pos_next_to(ball.cur_pos, key.cur_pos)
        if self.mission_text == PUT_BALL_NEXT_TO_KEY:
            return ball_next_to_key
        if self.mission_text == MOVE_BOX_TO_CORNER_THEN_PUT_BALL:
            return ball_next_to_key or self._in_corner(*purple_box.cur_pos)
        return False

    def _in_corner(self, x: int, y: int) -> bool:
        """A corner cell touches a wall horizontally and a wall vertically."""
        return (self._is_wall(x - 1, y) or self._is_wall(x + 1, y)) and (
            self._is_wall(x, y - 1) or self._is_wall(x, y + 1)
        )

    def _is_wall(self, x: int, y: int) -> bool:
        cell = self.grid.get(x, y)
        return cell is not None and cell.type == "wall"

    def _instruction(self):
        if self.mission_text == PUT_BALL_NEXT_TO_KEY:
            return PutNextInstr(ObjDesc("ball", "yellow"), ObjDesc("key", "red"))
        if self.mission_text == OPEN_DOOR_THEN_PICK_UP_BOX:
            return BeforeInstr(
                OpenInstr(ObjDesc("door", "green")), PickupInstr(ObjDesc("box", "blue"))
            )
        return JudgedByRewardMachine(self.mission_text)


register(
    id="BabyAI-ChosenMission-v0",
    entry_point="src.arm_fm.custom_envs.babyai_mission:ChosenMission",
)
