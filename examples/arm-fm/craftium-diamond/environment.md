# Craftium Diamond Gathering

## Environment

A 3D voxel world (VoxeLibre) played in first person, with movement, camera, digging, placement
and inventory-slot actions. The world is the same every episode: the agent starts in a birch
forest above a stone layer with iron below it, at midday; the day cycle lasts 5000 game steps.
Every reset restores the whole world, the inventory and the milestones. This environment is a
sparse-reward diamond task: the stock open world cut down to the wood-stone-iron-diamond chain.

The game grants tools; there is no crafting. Milestones must be reached in order, and each one
counts only nodes dug after the previous one:

1. Wood: digging 2 tree trunks grants a wooden pickaxe.
2. Stone: digging 3 stone nodes grants a stone pickaxe.
3. Iron: digging 3 iron ore nodes grants an iron pickaxe.
4. Diamond: digging 1 diamond ore node pays the only reward and ends the episode.

A dug node counts as a diamond, iron, stone or tree node by its name, checked in that order.
Only digs of the next milestone's kind move it forward; other digs only raise the dug-node
count, and the count restarts at each milestone. The milestone tools go to inventory slot 1.

The agent has 18 discrete actions: a leading no-op, `forward`, `backward`, `left`, `right`,
`jump`, `sneak`, `dig`, `place`, slots 1 to 5, and four mouse moves. Observations are grayscale
320x180 frames.

## Objective and episode boundary

The task gives sparse success only for obtaining a diamond. Its intended progression is wood,
stone, iron, then diamond. The environment pays reward 1.0 once, when the diamond milestone is
reached, and terminates then; reward and termination come on the step that first shows the
diamond milestone. Death terminates the episode without reward, and the episode is truncated
after 10,000 agent steps by default.

## Proposition semantics

Each proposition is the status of one milestone: it becomes true on the first transition
in which the agent reaches that milestone and stays true for the rest of the episode. It is
read from the cumulative milestone status, so it never repeats and no acquisition is lost
when several happen within one action. It does not read the RM state.

| id | kind | true when |
|---|---|---|
| `wood_acquired` | latch | the wood milestone has been reached |
| `stone_acquired` | latch | the stone milestone has been reached |
| `iron_acquired` | latch | the iron milestone has been reached |
| `diamond_acquired` | latch, final step | the diamond milestone has been reached; the episode ends on the same step |

## Constraints

- `stone_acquired` cannot become true before `wood_acquired`: only the next milestone's kind advances the chain.
- `iron_acquired` cannot become true before `stone_acquired`: same rule.
- `diamond_acquired` cannot become true before `iron_acquired`: same rule.
- `wood_acquired` cannot become false once true: the environment raises an error if a milestone flag goes back.
- `stone_acquired` cannot become false once true: same reason.
- `iron_acquired` cannot become false once true: same reason.
- `diamond_acquired` cannot become false once true: same reason.

## What the agent can and cannot do

- Can: move, jump, sneak, turn the camera, `dig`, `place`, pick inventory slots 1 to 5.
- Cannot: craft, since the action set has no crafting or menu action; the game grants tools instead.
- It is not known which tool the game requires to dig stone, iron ore or diamond ore, how many agent steps a real run takes, or whether one agent step can dig two nodes.
- Digs made before a milestone is next do not count toward it: iron ore dug before `stone_acquired` raises the iron dug-node count but not the iron milestone.
- `diamond_acquired` is the last step of a successful episode.
- Death ends the episode with reward 0, so any proposition still false then stays false.

## Example trace

A debug route, not a real dig: the agent does nothing, and the game grants each milestone at a
fixed game step as if it had dug the nodes. The game steps are fixed; the agent steps are
approximate. It is not known how a real digging run goes.

1. About 93 agent steps of no-op: no proposition changes.
2. Game step 300 (agent step about 94): `wood_acquired` true; wood dug-node count 2.
3. Game step 330 (agent step about 124): `stone_acquired` true; stone 3.
4. Game step 360 (agent step about 154): `iron_acquired` true; iron 3.
5. Game step 390 (agent step about 184): `diamond_acquired` true; reward 1.0; the episode terminates.

## Propositions
- `wood_acquired`: The agent has reached the wood milestone (dug 2 tree trunks and received the wooden pickaxe); stays true for the rest of the episode.
- `stone_acquired`: The agent has reached the stone milestone (after wood, dug 3 stone nodes and received the stone pickaxe); stays true for the rest of the episode.
- `iron_acquired`: The agent has reached the iron milestone (after stone, dug 3 iron ore nodes and received the iron pickaxe); stays true for the rest of the episode.
- `diamond_acquired`: The agent has reached the diamond milestone (after iron, dug a diamond ore node), which ends the episode; stays true until then.

## Example tasks

- Eventually acquire a diamond.
- Acquire wood before stone.
- Acquire stone before iron.
- Acquire iron before a diamond.
