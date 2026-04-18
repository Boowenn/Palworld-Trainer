local UEHelpers = require("UEHelpers")

local ModName = "PalworldTrainerBridge"
local Version = "1.1.2"
local LastFindQuery = nil
local LogWriteHealthy = true
local LastLogFailureShown = false

local function normalize_path(path)
    return tostring(path or ""):gsub("\\", "/")
end

local function dedupe_paths(paths)
    local result = {}
    local seen = {}
    for _, path in ipairs(paths) do
        local normalized = normalize_path(path)
        if normalized ~= "" and not seen[normalized] then
            seen[normalized] = true
            table.insert(result, normalized)
        end
    end
    return result
end

local function detect_mod_root()
    if not debug or not debug.getinfo then
        return ""
    end

    local info = debug.getinfo(1, "S")
    local source = info and info.source or ""
    if type(source) ~= "string" or source == "" then
        return ""
    end
    if source:sub(1, 1) == "@" then
        source = source:sub(2)
    end

    source = normalize_path(source)
    local script_dir = source:match("^(.*)/[^/]+$")
    if not script_dir then
        return ""
    end

    return script_dir:match("^(.*)/Scripts$") or script_dir
end

local ModRoot = detect_mod_root()
local PathRoots = dedupe_paths({
    ModRoot,
    "Mods/PalworldTrainerBridge",
    "Mods/NativeMods/UE4SS/Mods/PalworldTrainerBridge",
})

local function candidate_paths(filename)
    local result = {}
    for _, root in ipairs(PathRoots) do
        table.insert(result, string.format("%s/%s", root, filename))
    end
    return result
end

local function resolve_read_path(filename)
    local candidates = candidate_paths(filename)
    for _, path in ipairs(candidates) do
        local handle = io.open(path, "r")
        if handle then
            handle:close()
            return path
        end
    end
    return candidates[1]
end

local function resolve_write_path(filename)
    local candidates = candidate_paths(filename)
    for _, path in ipairs(candidates) do
        local handle = io.open(path, "a+")
        if handle then
            handle:close()
            return path
        end
    end
    return candidates[1]
end
local PresetQueries = {
    {
        key = "characters",
        title = "Nearby Characters",
        query = "Character",
        description = "Broad replicated character scan for UE Character-derived actors.",
        source = "UE base class",
    },
    {
        key = "controllers",
        title = "Player Controllers",
        query = "PlayerController",
        description = "Useful for validating controller presence on the local client.",
        source = "UE base class",
    },
    {
        key = "pal_player_controller",
        title = "Pal Player Controller",
        query = "BP_PalPlayerController_C",
        description = "Asset-derived Palworld player controller class.",
        source = "Manifest-derived asset name",
    },
    {
        key = "pal_spawners",
        title = "Pal Spawners",
        query = "BP_PalSpawner_Standard_C",
        description = "Asset-derived standard Pal spawn points.",
        source = "Manifest-derived asset name",
    },
    {
        key = "npc_spawners",
        title = "NPC Spawners",
        query = "BP_MonoNPCSpawner_C",
        description = "Asset-derived NPC spawner class.",
        source = "Manifest-derived asset name",
    },
    {
        key = "supply_spawners",
        title = "Supply Spawners",
        query = "BP_SupplySpawnerBase_C",
        description = "Asset-derived supply drop spawner base class.",
        source = "Manifest-derived asset name",
    },
    {
        key = "pal_managers",
        title = "Pal Managers",
        query = "BP_PalCharacterManager_C",
        description = "Asset-derived character manager class for world-level checks.",
        source = "Manifest-derived asset name",
    },
}

local function append_session_line(message)
    local session_log_path = resolve_write_path("session.log")
    local handle = io.open(session_log_path, "a+")
    if not handle then
        return false, "unable to open session log"
    end

    handle:write(string.format("[%s] [%s] %s\n", os.date("%Y-%m-%d %H:%M:%S"), ModName, message))
    handle:close()
    return true, nil
end

local function log(message)
    print(string.format("[%s] %s\n", ModName, message))

    local ok, err = append_session_line(message)
    LogWriteHealthy = ok
    if not ok and not LastLogFailureShown then
        LastLogFailureShown = true
        print(string.format("[%s] Session log write failed: %s\n", ModName, tostring(err)))
    elseif ok then
        LastLogFailureShown = false
    end
end

local function get_player()
    local player = UEHelpers.GetPlayer()
    if player and player:IsValid() then
        return player
    end
    return CreateInvalidObject()
end

local function get_player_controller()
    local controller = UEHelpers.GetPlayerController()
    if controller and controller:IsValid() then
        return controller
    end
    return CreateInvalidObject()
end

local function format_vector(vector)
    return string.format("X=%.1f Y=%.1f Z=%.1f", vector.X, vector.Y, vector.Z)
end

local function normalize_key(value)
    if not value then
        return ""
    end
    return string.lower(tostring(value))
end

local function try_get_location(object)
    if not object or not object:IsValid() then
        return nil
    end

    local ok, value = pcall(function()
        return object:K2_GetActorLocation()
    end)

    if ok then
        return value
    end
    return nil
end

local function distance_between(a, b)
    local dx = a.X - b.X
    local dy = a.Y - b.Y
    local dz = a.Z - b.Z
    return math.sqrt(dx * dx + dy * dy + dz * dz)
end

local function clamp_limit(value, fallback, max_value)
    local parsed = tonumber(value)
    if not parsed then
        return fallback
    end

    parsed = math.floor(parsed)
    if parsed < 1 then
        return 1
    end
    if parsed > max_value then
        return max_value
    end
    return parsed
end

local function safe_name(object)
    if object and object:IsValid() then
        return object:GetFullName()
    end
    return "<invalid>"
end

local function safe_class_name(object)
    if object and object:IsValid() then
        local ok, class_object = pcall(function()
            return object:GetClass()
        end)
        if ok and class_object and class_object:IsValid() then
            return class_object:GetFullName()
        end
    end
    return "<unknown class>"
end

local function build_rows(objects, limit)
    local rows = {}
    local player = get_player()
    local player_location = try_get_location(player)

    for _, object in ipairs(objects or {}) do
        if object and object:IsValid() then
            local location = try_get_location(object)
            local distance_meters = nil

            if player_location and location then
                distance_meters = distance_between(player_location, location) / 100.0
            end

            table.insert(rows, {
                name = safe_name(object),
                class_name = safe_class_name(object),
                location = location and format_vector(location) or "n/a",
                distance_meters = distance_meters,
            })
        end
    end

    table.sort(rows, function(left, right)
        if left.distance_meters and right.distance_meters then
            return left.distance_meters < right.distance_meters
        end
        if left.distance_meters then
            return true
        end
        if right.distance_meters then
            return false
        end
        return left.name < right.name
    end)

    local total = #rows
    while #rows > limit do
        table.remove(rows)
    end

    return rows, total
end

local function print_rows(title, rows, total)
    log(string.format("%s (%d shown / %d total)", title, #rows, total))
    for index, row in ipairs(rows) do
        local distance_text = row.distance_meters and string.format("%.1fm", row.distance_meters) or "n/a"
        log(string.format("[%d] %s | %s | %s | %s", index, distance_text, row.location, row.class_name, row.name))
    end
end

local function resolve_preset(preset_key)
    local normalized = normalize_key(preset_key)
    for _, preset in ipairs(PresetQueries) do
        if preset.key == normalized then
            return preset
        end
    end
    return nil
end

local function print_presets()
    log("Available presets:")
    for _, preset in ipairs(PresetQueries) do
        log(string.format("%s => %s | %s | %s", preset.key, preset.query, preset.title, preset.source))
    end
end

local function print_log_status()
    log("Session log path: " .. resolve_write_path("session.log"))
    log("Session log health: " .. (LogWriteHealthy and "OK" or "Degraded"))
end

local function clear_session_log()
    local session_log_path = resolve_write_path("session.log")
    local handle = io.open(session_log_path, "w")
    if not handle then
        log("Unable to clear the session log file.")
        return true
    end

    handle:write("")
    handle:close()
    LogWriteHealthy = true
    LastLogFailureShown = false
    log("Session log cleared: " .. session_log_path)
    return true
end

local function print_status()
    local player = get_player()
    local controller = get_player_controller()

    log(string.format("Bridge version: %s", Version))
    log(string.format("PlayerController valid: %s", tostring(controller:IsValid())))
    log(string.format("Player valid: %s", tostring(player:IsValid())))

    if player:IsValid() then
        local location = player:K2_GetActorLocation()
        log("Player location: " .. format_vector(location))
    end
end

local function print_world_snapshot()
    local world = UEHelpers.GetWorld()
    local level = UEHelpers.GetPersistentLevel()
    local game_state = UEHelpers.GetGameStateBase()
    local players = UEHelpers.GetAllPlayers()

    log(string.format("Bridge version: %s", Version))
    log("World: " .. safe_name(world))
    log("Persistent level: " .. safe_name(level))
    log("Game state: " .. safe_name(game_state))
    log(string.format("Replicated players: %d", #players))

    local player = get_player()
    if player:IsValid() then
        local location = player:K2_GetActorLocation()
        log("Local player location: " .. format_vector(location))
    end
end

local function print_player_snapshot(limit)
    local players = UEHelpers.GetAllPlayers()
    local rows, total = build_rows(players, limit)
    print_rows("Nearby replicated players", rows, total)
end

local function run_find_query(short_class_name, limit, label)
    if not short_class_name or short_class_name == "" then
        log("Usage: pt_find <ShortClassName> [limit]")
        return true
    end

    local objects = FindAllOf(short_class_name)
    if not objects or #objects == 0 then
        log(string.format("FindAllOf('%s') returned no objects.", short_class_name))
        LastFindQuery = {
            class_name = short_class_name,
            limit = limit,
            label = label or short_class_name,
        }
        return true
    end

    local rows, total = build_rows(objects, limit)
    print_rows(label or string.format("FindAllOf('%s')", short_class_name), rows, total)

    LastFindQuery = {
        class_name = short_class_name,
        limit = limit,
        label = label or short_class_name,
    }
    return true
end

local function repeat_last_find()
    if not LastFindQuery then
        log("No previous pt_find query is cached yet.")
        return true
    end

    return run_find_query(LastFindQuery.class_name, LastFindQuery.limit, LastFindQuery.label)
end

-- ===========================================================================
-- Cheat engine
-- ===========================================================================
--
-- Persistent toggle state mirrored from the Python GUI via toggles.json.
-- Every ~200 ms we re-read the file (cheap) and re-apply any "force value"
-- style cheats (god mode, infinite stamina, move speed multiplier, ...).
-- One-shot style cheats (map defog, give passives) are exposed as pt_*
-- console commands and should be triggered manually from the in-game UE4SS
-- console — we do NOT want to run them every tick.
--
-- Field names below are best-effort guesses against Palworld's UObject
-- layout. If something doesn't work, the `pt_dump` command prints the
-- player's full class hierarchy + property names + component list so we
-- can correct the names in the next iteration.

local Cheats = {
    godmode = false,
    inf_stamina = false,
    weight_zero = false,
    inf_ammo = false,
    no_durability = false,
    speed_multiplier = 1.0,
    jump_multiplier = 1.0,
}

local BaseMovement = {
    walk = nil,
    run = nil,
    sprint = nil,
    jump = nil,
}

local TickCounter = 0
local LastTogglesRead = 0
local LastStatusWrite = 0
local LastRequestId = nil

local function safe_get_prop(object, name)
    if not object or not object:IsValid() then
        return nil
    end
    local ok, value = pcall(function()
        return object[name]
    end)
    if ok then
        return value
    end
    return nil
end

local function safe_set_prop(object, name, value)
    if not object or not object:IsValid() then
        return false
    end
    local ok = pcall(function()
        object[name] = value
    end)
    return ok
end

local function try_components(player, class_names)
    for _, class_name in ipairs(class_names) do
        local ok, component = pcall(function()
            return player:GetComponentByClass(class_name)
        end)
        if ok and component and component:IsValid() then
            return component
        end
    end
    return nil
end

local function parse_bool(text, key)
    local value = text:match('"' .. key .. '"%s*:%s*([%a]+)')
    if value == "true" then
        return true
    end
    if value == "false" then
        return false
    end
    return nil
end

local function parse_number(text, key)
    local value = text:match('"' .. key .. '"%s*:%s*([%-%.%d]+)')
    return tonumber(value)
end

local function parse_string(text, key)
    return text:match('"' .. key .. '"%s*:%s*"([^"]+)"')
end

local function write_status()
    local status_path = resolve_write_path("status.json")
    local handle = io.open(status_path, "w")
    if not handle then
        return false
    end

    local player = get_player()
    if not player:IsValid() then
        handle:write(string.format(
            '{\n  "player_valid": false,\n  "bridge_version": "%s"\n}\n',
            Version
        ))
        handle:close()
        return true
    end

    local location = player:K2_GetActorLocation()
    handle:write(string.format(
        '{\n  "player_valid": true,\n  "bridge_version": "%s",\n  "position_x": %.3f,\n  "position_y": %.3f,\n  "position_z": %.3f\n}\n',
        Version,
        location.X,
        location.Y,
        location.Z
    ))
    handle:close()
    return true
end

local function read_request()
    local handle = io.open(resolve_read_path("request.json"), "r")
    if not handle then
        return nil
    end

    local text = handle:read("*a") or ""
    handle:close()
    if text == "" then
        return nil
    end

    local action = parse_string(text, "action")
    local request_id = parse_number(text, "request_id")
    if not action or request_id == nil then
        return nil
    end

    return {
        action = action,
        request_id = request_id,
        x = parse_number(text, "x"),
        y = parse_number(text, "y"),
        z = parse_number(text, "z"),
        enabled = parse_bool(text, "enabled"),
    }
end

local function process_request()
    local request = read_request()
    if not request then
        return
    end
    if LastRequestId ~= nil and request.request_id == LastRequestId then
        return
    end
    LastRequestId = request.request_id

    if request.action == "teleport" then
        local player = get_player()
        if not player:IsValid() then
            log(string.format("Teleport request #%d ignored: local player not ready.", request.request_id))
            return
        end

        local root = safe_get_prop(player, "RootComponent")
        local location = player:K2_GetActorLocation()
        local rotation = player:K2_GetActorRotation()
        if root and root:IsValid() then
            location = root:K2_GetComponentLocation()
            rotation = root:K2_GetComponentRotation()
        end

        if request.x ~= nil then
            location.X = request.x
        end
        if request.y ~= nil then
            location.Y = request.y
        end
        if request.z ~= nil then
            location.Z = request.z
        end

        local hit_result = {}
        local ok = pcall(function()
            player:K2_SetActorLocationAndRotation(location, rotation, false, hit_result, false)
        end)
        if ok then
            log(string.format("Teleport request #%d => %s", request.request_id, format_vector(location)))
            pcall(write_status)
        else
            log(string.format("Teleport request #%d failed.", request.request_id))
        end
    elseif request.action == "set_fly" then
        local player = get_player()
        if not player:IsValid() then
            log(string.format("Fly request #%d ignored: local player not ready.", request.request_id))
            return
        end

        local move = safe_get_prop(player, "CharacterMovement")
        if not move or not move:IsValid() then
            log(string.format("Fly request #%d ignored: CharacterMovement missing.", request.request_id))
            return
        end

        local desired_mode = request.enabled and 5 or 1
        local ok = pcall(function()
            if move.SetMovementMode then
                move:SetMovementMode(desired_mode, 0)
            end
        end)
        safe_set_prop(move, "MovementMode", desired_mode)
        safe_set_prop(move, "CustomMovementMode", 0)

        if ok then
            log(string.format("Fly request #%d => mode %d", request.request_id, desired_mode))
        else
            log(string.format("Fly request #%d => fallback mode %d", request.request_id, desired_mode))
        end
        pcall(write_status)
    end
end

local function read_toggles()
    local handle = io.open(resolve_read_path("toggles.json"), "r")
    if not handle then
        return false
    end

    local text = handle:read("*a") or ""
    handle:close()
    if text == "" then
        return false
    end

    local function apply_bool(key)
        local parsed = parse_bool(text, key)
        if parsed ~= nil then
            Cheats[key] = parsed
        end
    end
    local function apply_num(key)
        local parsed = parse_number(text, key)
        if parsed ~= nil then
            Cheats[key] = parsed
        end
    end

    apply_bool("godmode")
    apply_bool("inf_stamina")
    apply_bool("weight_zero")
    apply_bool("inf_ammo")
    apply_bool("no_durability")
    apply_num("speed_multiplier")
    apply_num("jump_multiplier")
    return true
end

local function describe_cheats()
    return string.format(
        "god=%s stam=%s weight0=%s ammo=%s dura=%s speed=%.2f jump=%.2f",
        tostring(Cheats.godmode),
        tostring(Cheats.inf_stamina),
        tostring(Cheats.weight_zero),
        tostring(Cheats.inf_ammo),
        tostring(Cheats.no_durability),
        Cheats.speed_multiplier,
        Cheats.jump_multiplier
    )
end

local function capture_base_movement(move)
    if not move or not move:IsValid() then
        return
    end

    local walk = safe_get_prop(move, "MaxWalkSpeed")
    local jump = safe_get_prop(move, "JumpZVelocity")

    -- Only capture once, and ignore obviously-modified (already multiplied) values
    if walk and walk > 0 and not BaseMovement.walk then
        BaseMovement.walk = walk
    end
    if jump and jump > 0 and not BaseMovement.jump then
        BaseMovement.jump = jump
    end
end

local function apply_movement_multipliers(player)
    local move = safe_get_prop(player, "CharacterMovement")
    if not move or not move:IsValid() then
        return
    end

    capture_base_movement(move)

    if BaseMovement.walk then
        safe_set_prop(move, "MaxWalkSpeed", BaseMovement.walk * Cheats.speed_multiplier)
        safe_set_prop(move, "MaxWalkSpeedCrouched", BaseMovement.walk * Cheats.speed_multiplier * 0.5)
    end
    if BaseMovement.jump then
        safe_set_prop(move, "JumpZVelocity", BaseMovement.jump * Cheats.jump_multiplier)
    end
end

local function apply_godmode(player)
    if not Cheats.godmode then
        return
    end

    -- Try known Palworld parameter component class names.
    local comp = try_components(player, {
        "PalCharacterParameterComponent",
        "PalPlayerCharacterParameterComponent",
        "CharacterParameterComponent",
    })
    if comp then
        local max_hp = safe_get_prop(comp, "MaxHP") or safe_get_prop(comp, "HP_Max")
        if max_hp and max_hp > 0 then
            safe_set_prop(comp, "HP", max_hp)
            safe_set_prop(comp, "CurrentHP", max_hp)
        end
    end

    -- Fallback: direct pawn properties.
    local max_hp = safe_get_prop(player, "MaxHP")
    if max_hp and max_hp > 0 then
        safe_set_prop(player, "HP", max_hp)
        safe_set_prop(player, "CurrentHP", max_hp)
    end
end

local function apply_infinite_stamina(player)
    if not Cheats.inf_stamina then
        return
    end

    local comp = try_components(player, {
        "PalStaminaComponent",
        "PalCharacterStaminaComponent",
        "PalStatusComponent",
        "PalCharacterParameterComponent",
    })
    if comp then
        local max_sp = safe_get_prop(comp, "MaxSP")
            or safe_get_prop(comp, "SP_Max")
            or safe_get_prop(comp, "MaxStamina")
        if max_sp and max_sp > 0 then
            safe_set_prop(comp, "SP", max_sp)
            safe_set_prop(comp, "CurrentSP", max_sp)
            safe_set_prop(comp, "Stamina", max_sp)
        end
    end

    local pawn_max = safe_get_prop(player, "MaxSP") or safe_get_prop(player, "MaxStamina")
    if pawn_max and pawn_max > 0 then
        safe_set_prop(player, "SP", pawn_max)
        safe_set_prop(player, "Stamina", pawn_max)
    end
end

local function apply_weight_zero(player)
    if not Cheats.weight_zero then
        return
    end

    -- Palworld player inventory lives on a component. Try a few names.
    local inv = try_components(player, {
        "PalPlayerInventoryDataComponent",
        "PalInventoryDataComponent",
        "PalCharacterInventoryComponent",
    })
    if inv then
        -- We don't want an immovable player, so we bump MaxWeight to a huge
        -- number instead of touching CurrentWeight.
        safe_set_prop(inv, "MaxInventoryWeight", 99999999.0)
        safe_set_prop(inv, "MaxWeight", 99999999.0)
    end

    -- Fallback: parameter component often exposes max carry weight too.
    local param = try_components(player, {
        "PalCharacterParameterComponent",
        "PalPlayerCharacterParameterComponent",
    })
    if param then
        safe_set_prop(param, "MaxInventoryWeight", 99999999.0)
        safe_set_prop(param, "MaxWeight", 99999999.0)
    end
end

local function tick_apply_cheats()
    local player = get_player()
    if not player:IsValid() then
        return
    end

    pcall(function() apply_godmode(player) end)
    pcall(function() apply_infinite_stamina(player) end)
    pcall(function() apply_weight_zero(player) end)
    pcall(function() apply_movement_multipliers(player) end)
end

-- Diagnostic dump: print player class hierarchy + properties + components so
-- we can correct any wrong field guesses in the next iteration.
local function dump_player()
    local player = get_player()
    if not player:IsValid() then
        log("pt_dump: local player not ready")
        return
    end

    log("=== pt_dump ===")
    log("Player full name: " .. safe_name(player))

    pcall(function()
        local class = player:GetClass()
        local depth = 0
        while class and class:IsValid() and depth < 12 do
            log(string.format("class[%d]: %s", depth, class:GetFullName()))
            local ok, super = pcall(function()
                return class:GetSuperStruct()
            end)
            if not ok or not super or not super:IsValid() then
                break
            end
            class = super
            depth = depth + 1
        end
    end)

    pcall(function()
        local class = player:GetClass()
        if class and class:IsValid() and class.ForEachProperty then
            log("-- properties --")
            local count = 0
            class:ForEachProperty(function(prop)
                count = count + 1
                if count > 120 then
                    return LoopAction.Break
                end
                local ok, name = pcall(function()
                    return prop:GetFName():ToString()
                end)
                if ok then
                    log("prop: " .. tostring(name))
                end
                return LoopAction.Continue
            end)
            log(string.format("-- %d properties enumerated --", count))
        end
    end)

    local move = safe_get_prop(player, "CharacterMovement")
    if move and move:IsValid() then
        log("CharacterMovement: " .. safe_name(move))
        log("  MaxWalkSpeed: " .. tostring(safe_get_prop(move, "MaxWalkSpeed")))
        log("  JumpZVelocity: " .. tostring(safe_get_prop(move, "JumpZVelocity")))
    else
        log("CharacterMovement: <not found>")
    end

    local probe = {
        "PalCharacterParameterComponent",
        "PalPlayerCharacterParameterComponent",
        "PalStaminaComponent",
        "PalStatusComponent",
        "PalPlayerInventoryDataComponent",
        "PalInventoryDataComponent",
    }
    for _, class_name in ipairs(probe) do
        local comp = try_components(player, { class_name })
        log("component " .. class_name .. ": " .. (comp and safe_name(comp) or "<not found>"))
    end

    log("=== end pt_dump ===")
end

RegisterConsoleCommandHandler("pt_help", function(full_command, parameters, ar)
    log("Available commands:")
    log("pt_help   - print the available trainer bridge commands")
    log("pt_status - print trainer bridge and player status")
    log("pt_pos    - print the local player coordinates")
    log("pt_world  - print the world, level, and replicated player snapshot")
    log("pt_players [limit] - list nearby replicated player pawns")
    log("pt_find <ShortClassName> [limit] - run a generic FindAllOf scan")
    log("pt_presets - list the built-in scan presets")
    log("pt_scan <preset> [limit] - run a built-in preset query")
    log("pt_repeat - repeat the most recent pt_find query")
    log("pt_log_status - print the bridge session log health and path")
    log("pt_log_clear - clear the bridge session log")
    log("pt_cheats - print current cheat toggle state")
    log("pt_reload - re-read toggles.json from disk")
    log("pt_dump   - dump player class hierarchy + properties for diagnostics")
    log("Hotkeys: CTRL+F6 = pt_pos, CTRL+F7 = pt_world, CTRL+F8 = pt_repeat")
    return true
end)

RegisterConsoleCommandHandler("pt_status", function(full_command, parameters, ar)
    print_status()
    return true
end)

RegisterConsoleCommandHandler("pt_pos", function(full_command, parameters, ar)
    local player = get_player()
    if not player:IsValid() then
        log("Local player is not available yet.")
        return true
    end

    local location = player:K2_GetActorLocation()
    log("Player location: " .. format_vector(location))
    return true
end)

RegisterConsoleCommandHandler("pt_world", function(full_command, parameters, ar)
    print_world_snapshot()
    return true
end)

RegisterConsoleCommandHandler("pt_players", function(full_command, parameters, ar)
    local limit = clamp_limit(parameters[1], 8, 32)
    print_player_snapshot(limit)
    return true
end)

RegisterConsoleCommandHandler("pt_find", function(full_command, parameters, ar)
    local short_class_name = parameters[1]
    local limit = clamp_limit(parameters[2], 10, 64)
    return run_find_query(short_class_name, limit)
end)

RegisterConsoleCommandHandler("pt_presets", function(full_command, parameters, ar)
    print_presets()
    return true
end)

RegisterConsoleCommandHandler("pt_scan", function(full_command, parameters, ar)
    local preset_key = parameters[1]
    if not preset_key or preset_key == "" then
        log("Usage: pt_scan <preset> [limit]")
        print_presets()
        return true
    end

    local preset = resolve_preset(preset_key)
    if not preset then
        log("Unknown preset: " .. tostring(preset_key))
        print_presets()
        return true
    end

    local limit = clamp_limit(parameters[2], 10, 64)
    return run_find_query(preset.query, limit, string.format("Preset '%s' => %s", preset.key, preset.query))
end)

RegisterConsoleCommandHandler("pt_repeat", function(full_command, parameters, ar)
    return repeat_last_find()
end)

RegisterConsoleCommandHandler("pt_log_status", function(full_command, parameters, ar)
    print_log_status()
    return true
end)

RegisterConsoleCommandHandler("pt_log_clear", function(full_command, parameters, ar)
    return clear_session_log()
end)

RegisterConsoleCommandHandler("pt_cheats", function(full_command, parameters, ar)
    log("Cheat state: " .. describe_cheats())
    log("Toggles file: " .. resolve_read_path("toggles.json"))
    return true
end)

RegisterConsoleCommandHandler("pt_reload", function(full_command, parameters, ar)
    local ok = read_toggles()
    log(string.format("Reloaded toggles from disk: %s", tostring(ok)))
    log("Cheat state: " .. describe_cheats())
    return true
end)

RegisterConsoleCommandHandler("pt_dump", function(full_command, parameters, ar)
    dump_player()
    return true
end)

RegisterKeyBindAsync(Key.F6, { ModifierKey.CONTROL }, function()
    local player = get_player()
    if not player:IsValid() then
        log("CTRL+F6 pressed, but the local player is not ready yet.")
        return
    end

    local location = player:K2_GetActorLocation()
    log("CTRL+F6 => " .. format_vector(location))
end)

RegisterKeyBindAsync(Key.F7, { ModifierKey.CONTROL }, function()
    print_world_snapshot()
end)

RegisterKeyBindAsync(Key.F8, { ModifierKey.CONTROL }, function()
    if not LastFindQuery then
        log("CTRL+F8 has no cached pt_find query yet. Falling back to pt_players 8.")
        print_player_snapshot(8)
        return
    end

    repeat_last_find()
end)

RegisterKeyBindAsync(Key.F9, { ModifierKey.CONTROL }, function()
    ExecuteInGameThread(function()
        dump_player()
    end)
end)

RegisterHook("/Script/Engine.PlayerController:ClientRestart", function(self, new_pawn)
    ExecuteInGameThread(function()
        print_status()
        -- Reset cached base movement values so next tick re-captures them.
        BaseMovement.walk = nil
        BaseMovement.jump = nil
        BaseMovement.run = nil
        BaseMovement.sprint = nil
        read_toggles()
        write_status()
    end)
end)

LoopAsync(200, function()
    TickCounter = TickCounter + 1

    -- Re-read toggles every ~2 seconds so GUI checkbox flips propagate
    -- without needing a pt_reload call.
    if TickCounter - LastTogglesRead >= 10 then
        LastTogglesRead = TickCounter
        pcall(read_toggles)
    end

    if TickCounter - LastStatusWrite >= 10 then
        LastStatusWrite = TickCounter
        pcall(write_status)
    end

    pcall(process_request)
    pcall(tick_apply_cheats)
    return false
end)

ExecuteInGameThread(function()
    log(string.format("Bridge %s loaded.", Version))
    log("Use pt_help, pt_cheats, pt_dump, or the hotkeys CTRL+F6 / F7 / F8 / F9 in-game.")
    pcall(read_toggles)
    pcall(write_status)
    log("Initial cheat state: " .. describe_cheats())
end)
