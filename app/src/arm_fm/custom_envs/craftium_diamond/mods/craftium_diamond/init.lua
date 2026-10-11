-- Craftium diamond task, cut down from Craftium's OpenWorld mod.
--
-- The game grants the next pickaxe at each milestone (wood, stone, iron). Death ends the episode
-- without reward. The diamond reward and its termination are not sent through Craftium's
-- reward/termination flags (the client reads them without a lock against this thread): the Python
-- side pays 1.0 and terminates on the step whose snapshot first shows the diamond milestone.
-- Every engine step the mod writes an atomic JSON snapshot of the cumulative state in the world
-- directory, which the Python side reads after each step() and reset().

local settings = core.settings
local snapshot_path = core.get_worldpath() .. "/craftium_state.json"

-- Set by Python on every reset; lets the reader reject a snapshot of another episode.
local episode = tonumber(settings:get("craftium_episode")) or 0

-- Items of the initial inventory (as in OpenWorld).
local INIT_ITEMS = { "mcl_tools:axe_stone", "mcl_torches:torch 256" }

-- Milestones in the order they must be reached. A dug node counts toward the first category
-- whose `match` substring its name contains (rarest first, so iron ore is not "stone").
-- `required` is the number of dug nodes that completes the milestone (OpenWorld's values).
local MILESTONES = {
	{ name = "wood", match = "tree", required = 2, tool = "mcl_tools:pick_wood" },
	{ name = "stone", match = "stone", required = 3, tool = "mcl_tools:pick_stone" },
	{ name = "iron", match = "iron", required = 3, tool = "mcl_tools:pick_iron" },
	{ name = "diamond", match = "diamond", required = 1 },
}
local MATCH_ORDER = { 4, 3, 2, 1 }
local REQUIRED = {}
for _, milestone in ipairs(MILESTONES) do
	REQUIRED[milestone.name] = milestone.required
end

-- Cumulative state of this episode.
local inventory = { wood = 0, stone = 0, iron = 0, diamond = 0 } -- nodes dug per category
local milestones = { wood = false, stone = false, iron = false, diamond = false }
local current = 1 -- index of the next milestone to reach
local progress = 0 -- dug nodes of the next milestone's category since the previous milestone
local step = 0 -- engine steps since the player joined

-- Debug route: "wood@10,stone@10,iron@25,diamond@40" grants a milestone at that engine step,
-- exactly as if the agent had dug the required nodes. Several entries may share a step.
local route = {}
for item, at in string.gmatch(settings:get("craftium_debug_route") or "", "(%a+)@(%d+)") do
	route[#route + 1] = { name = item, at = tonumber(at), done = false }
end

local function write_snapshot()
	local snapshot = {
		episode = episode,
		step = step,
		inventory = inventory,
		milestones = milestones,
	}
	if not core.safe_file_write(snapshot_path, core.write_json(snapshot)) then
		error("craftium_diamond: cannot write " .. snapshot_path)
	end
end

-- The new pickaxe goes in slot 1, the slot selected at spawn (the engine has no server-side
-- way to change the selected slot; the agent can still pick another with its slot actions).
local function grant_tool(player, tool)
	local inv = player:get_inventory()
	inv:set_list("main", {})
	inv:add_item("main", tool)
	for _, item in ipairs(INIT_ITEMS) do
		inv:add_item("main", item)
	end
end

local function complete_milestone()
	local milestone = MILESTONES[current]
	milestones[milestone.name] = true
	if milestone.tool then
		for _, player in pairs(core.get_connected_players()) do
			grant_tool(player, milestone.tool)
		end
		current = current + 1
		progress = 0
	end
end

-- Count one dug node of a category; only the next milestone's category advances the chain.
local function record_dig(category)
	inventory[category] = inventory[category] + 1
	local milestone = MILESTONES[current]
	if milestone.name == category and not milestones[category] then
		progress = progress + 1
		if progress >= milestone.required then
			complete_milestone()
		end
	end
end

core.register_on_dignode(function(_pos, node)
	for _, index in ipairs(MATCH_ORDER) do
		local milestone = MILESTONES[index]
		if string.find(node.name, milestone.match, 1, true) then
			record_dig(milestone.name)
			break
		end
	end
	write_snapshot()
end)

core.register_on_joinplayer(function(player)
	core.set_timeofday(0.5) -- start the episode at midday
	player:hud_set_flags({ crosshair = false, basic_debug = false, chat = false })
	local inv = player:get_inventory()
	for _, item in ipairs(INIT_ITEMS) do
		inv:add_item("main", item)
	end
	player:set_pos({ x = 120, z = 92, y = 16.5 })
end)

-- Death ends the episode without reward.
core.register_on_dieplayer(function()
	set_termination()
end)

local timeofday = 0.5
local TIMEOFDAY_STEP = 1 / 5000 -- the day/night cycle lasts 5000 engine steps

core.register_globalstep(function()
	if #core.get_connected_players() == 0 then
		return
	end
	step = step + 1
	timeofday = (timeofday + TIMEOFDAY_STEP) % 1.0
	core.set_timeofday(timeofday)

	for _, entry in ipairs(route) do
		if not entry.done and step >= entry.at then
			entry.done = true
			for _ = 1, REQUIRED[entry.name] do
				record_dig(entry.name)
			end
		end
	end
	write_snapshot()
end)
