local UEHelpers = require("UEHelpers")

local ModName = "PalworldTrainerBridge"
local Version = "1.2.7"
local LastFindQuery = nil
local LogWriteHealthy = true
local LastLogFailureShown = false
local HiddenCommandRegistry = nil
local HiddenCommandRegistryPath = nil
local HiddenRegistryReady = false
local ChatSuppressionReady = false
local ChatSuppressionProbeLogged = false
local ClientCheatModulesLogged = false
local ClientCheatPackagePathConfigured = false
local ClientCheatScriptsRoot = nil
local KnownClientCheatModules = nil
local KnownClientCheatModuleNames = {
    "core.commands",
    "core.handler",
    "core.logic",
    "core.technology",
    "enums.itemdata",
    "enums.npcdata",
    "enums.paldata",
    "enums.technologydata",
}

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

local function path_dirname(path)
    local normalized = normalize_path(path)
    return normalized:match("^(.*)/[^/]+$") or ""
end

local ModRoot = detect_mod_root()
local ModsRoot = path_dirname(ModRoot)
local PathRoots = dedupe_paths({
    ModRoot,
    "Mods/PalworldTrainerBridge",
    "Mods/NativeMods/UE4SS/Mods/PalworldTrainerBridge",
})
local ClientCheatRootCandidates = dedupe_paths({
    ModsRoot ~= "" and string.format("%s/ClientCheatCommands", ModsRoot) or "",
    "Mods/ClientCheatCommands",
    "Mods/NativeMods/UE4SS/Mods/ClientCheatCommands",
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

local function detect_client_cheat_scripts_root()
    for _, root in ipairs(ClientCheatRootCandidates) do
        local candidate = string.format("%s/Scripts/main.lua", root)
        local handle = io.open(candidate, "r")
        if handle then
            handle:close()
            return string.format("%s/Scripts", root)
        end
    end
    return nil
end

local function ensure_client_cheat_package_path()
    if ClientCheatPackagePathConfigured and ClientCheatScriptsRoot then
        return true, ClientCheatScriptsRoot
    end
    if type(package) ~= "table" then
        return false, nil
    end

    local scripts_root = ClientCheatScriptsRoot or detect_client_cheat_scripts_root()
    if not scripts_root then
        return false, nil
    end

    local patterns = {
        string.format("%s/?.lua", scripts_root),
        string.format("%s/?/init.lua", scripts_root),
    }
    local package_path = tostring(package.path or "")
    for _, pattern in ipairs(patterns) do
        if not package_path:find(pattern, 1, true) then
            package_path = pattern .. ";" .. package_path
        end
    end
    package.path = package_path
    ClientCheatScriptsRoot = scripts_root
    ClientCheatPackagePathConfigured = true
    return true, scripts_root
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
local HiddenCommandNames = {
    "settime",
    "giveexp",
    "unstuck",
    "help",
    "unlocktech",
    "fly",
    "getpos",
    "unlockalltech",
    "giveme",
    "unlockft",
    "time",
    "give",
    "spawn",
    "exp",
    "goto",
}
local HiddenCommandLookup = {}
for _, command_name in ipairs(HiddenCommandNames) do
    HiddenCommandLookup[command_name] = true
end

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
    local _, value_start = text:find('"' .. key .. '"%s*:%s*"', 1)
    if not value_start then
        return nil
    end

    local parts = {}
    local index = value_start + 1
    while index <= #text do
        local ch = text:sub(index, index)
        if ch == '"' then
            return table.concat(parts)
        end
        if ch == "\\" then
            index = index + 1
            local escaped = text:sub(index, index)
            if escaped == '"' or escaped == "\\" or escaped == "/" then
                table.insert(parts, escaped)
            elseif escaped == "b" then
                table.insert(parts, "\b")
            elseif escaped == "f" then
                table.insert(parts, "\f")
            elseif escaped == "n" then
                table.insert(parts, "\n")
            elseif escaped == "r" then
                table.insert(parts, "\r")
            elseif escaped == "t" then
                table.insert(parts, "\t")
            elseif escaped == "u" then
                local hex = text:sub(index + 1, index + 4)
                if hex:match("^%x%x%x%x$") and utf8 and utf8.char then
                    local codepoint = tonumber(hex, 16)
                    local ok, decoded = pcall(utf8.char, codepoint)
                    if ok then
                        table.insert(parts, decoded)
                    end
                    index = index + 4
                end
            elseif escaped ~= "" then
                table.insert(parts, escaped)
            end
        else
            table.insert(parts, ch)
        end
        index = index + 1
    end
    return nil
end

local function trim(text)
    return tostring(text or ""):match("^%s*(.-)%s*$")
end

local function normalize_hidden_name(value)
    if type(value) ~= "string" then
        return nil
    end
    local normalized = string.lower(trim(value))
    if normalized == "" then
        return nil
    end
    return normalized
end

local function starts_with_hidden_chat_command(text)
    local normalized = trim(text)
    if normalized == "" then
        return false
    end
    while normalized:sub(1, 1) == "/" do
        normalized = trim(normalized:sub(2))
    end
    return normalized:sub(1, 2) == "@!"
end

local function path_mentions_client_cheat(text)
    local normalized = normalize_hidden_name(text)
    if not normalized then
        return false
    end
    return normalized:find("clientcheatcommands", 1, true) ~= nil
        or normalized:find("client_cheat_commands", 1, true) ~= nil
        or normalized:find("clientcheat", 1, true) ~= nil
end

local function append_unique(list, seen, value)
    if not value or seen[value] then
        return
    end
    seen[value] = true
    table.insert(list, value)
end

local function join_hidden_hits(values)
    if not values or #values == 0 then
        return "-"
    end
    return table.concat(values, ",")
end

local function has_hidden_callable_shape(value)
    local function get_meta(candidate)
        local getter = nil
        if debug and debug.getmetatable then
            getter = debug.getmetatable
        elseif getmetatable then
            getter = getmetatable
        end
        if not getter then
            return nil
        end

        local ok, meta = pcall(getter, candidate)
        if ok and type(meta) == "table" then
            return meta
        end
        return nil
    end

    local function meta_has_callable(meta)
        if type(meta) ~= "table" then
            return false
        end
        if type(rawget(meta, "__call")) == "function" then
            return true
        end
        local checked = 0
        for key, entry in next, meta do
            checked = checked + 1
            if type(entry) == "function" then
                return true
            end
            if type(key) == "string" then
                local normalized_key = string.lower(key)
                if normalized_key == "__call"
                    or normalized_key == "__index"
                    or normalized_key == "handler"
                    or normalized_key == "execute"
                    or normalized_key == "exec"
                    or normalized_key == "callback"
                    or normalized_key == "run"
                    or normalized_key == "func"
                then
                    return true
                end
            end
            if checked >= 24 then
                break
            end
        end
        return false
    end

    if type(value) == "function" then
        return true
    end
    if type(value) ~= "table" then
        return false
    end

    local meta = get_meta(value)
    if meta_has_callable(meta) then
        return true
    end

    local inspected = 0
    for key, entry in next, value do
        inspected = inspected + 1
        if type(entry) == "function" then
            return true
        end
        if type(entry) == "table" then
            local entry_meta = get_meta(entry)
            if meta_has_callable(entry_meta) then
                return true
            end
            local nested_checked = 0
            for _, nested_entry in next, entry do
                nested_checked = nested_checked + 1
                if type(nested_entry) == "function" then
                    return true
                end
                if nested_checked >= 16 then
                    break
                end
            end
        end
        if type(key) == "string" then
            local normalized_key = string.lower(key)
            if normalized_key == "handler"
                or normalized_key == "execute"
                or normalized_key == "exec"
                or normalized_key == "callback"
                or normalized_key == "run"
                or normalized_key == "func"
            then
                return true
            end
        end
        if inspected >= 32 then
            break
        end
    end
    return false
end

local function extract_hidden_descriptor_name(candidate)
    if type(candidate) ~= "table" then
        return nil
    end

    for _, key in ipairs({ "name", "Name", "command", "Command", "cmd", "Cmd" }) do
        local normalized = normalize_hidden_name(rawget(candidate, key))
        if normalized ~= nil then
            return normalized
        end
    end

    return normalize_hidden_name(rawget(candidate, 1))
end

local function describe_function(func)
    if not debug or not debug.getinfo then
        return "function"
    end

    local ok, info = pcall(debug.getinfo, func, "u")
    if not ok or type(info) ~= "table" then
        return "function"
    end
    return string.format(
        "function(nparams=%s,vararg=%s)",
        tostring(info.nparams),
        tostring(info.isvararg)
    )
end

local function describe_hidden_entry(value)
    local value_type = type(value)
    if value_type == "function" then
        return describe_function(value)
    end
    if value_type ~= "table" then
        return value_type
    end

    local parts = {}
    local count = 0
    for key, entry in next, value do
        count = count + 1
        if count > 6 then
            table.insert(parts, "...")
            break
        end
        local piece = tostring(key) .. "=" .. type(entry)
        if type(entry) == "function" then
            piece = tostring(key) .. "=" .. describe_function(entry)
        end
        table.insert(parts, piece)
    end
    return "table{" .. table.concat(parts, ", ") .. "}"
end

local function log_client_cheat_module_summary(module_name, value)
    log(string.format("CCC module loaded: %s => %s", tostring(module_name), describe_hidden_entry(value)))

    if type(value) == "table" then
        local count = 0
        for key, entry in next, value do
            count = count + 1
            if count > 12 then
                log("  ...")
                break
            end

            local suffix = ""
            if type(entry) == "function" and debug and debug.getinfo then
                local ok, info = pcall(debug.getinfo, entry, "S")
                if ok and type(info) == "table" then
                    local source = tostring(info.source or "")
                    if source ~= "" then
                        suffix = " @" .. normalize_path(source)
                    end
                end
            end
            log(string.format("  %s => %s%s", tostring(key), describe_hidden_entry(entry), suffix))
        end
    elseif type(value) == "function" and debug and debug.getupvalue then
        for index = 1, 12 do
            local upvalue_name, upvalue_value = debug.getupvalue(value, index)
            if upvalue_name == nil then
                break
            end
            log(string.format(
                "  upvalue[%d] %s => %s",
                index,
                tostring(upvalue_name),
                describe_hidden_entry(upvalue_value)
            ))
        end
    end
end

local function load_client_cheat_module(module_name)
    local ok_path, scripts_root = ensure_client_cheat_package_path()
    if not ok_path or not scripts_root then
        return false, "scripts_root_missing", "bootstrap"
    end

    local ok_require, required_value = pcall(require, module_name)
    if ok_require and required_value ~= nil then
        return true, required_value, "require"
    end

    if not loadfile then
        return false, tostring(required_value), "require"
    end

    local module_path = string.format("%s/%s.lua", scripts_root, module_name:gsub("%.", "/"))
    local chunk, chunk_error = loadfile(module_path)
    if not chunk then
        return false, tostring(chunk_error or required_value), "loadfile"
    end

    local ok_chunk, result = pcall(chunk)
    if not ok_chunk then
        return false, tostring(result), "loadfile"
    end

    if type(package) == "table" and type(package.loaded) == "table" then
        package.loaded[module_name] = result
    end
    return true, result, "loadfile"
end

local function load_known_client_cheat_modules()
    if KnownClientCheatModules ~= nil then
        return KnownClientCheatModules
    end

    KnownClientCheatModules = {}
    for _, module_name in ipairs(KnownClientCheatModuleNames) do
        local ok, value, mode = load_client_cheat_module(module_name)
        if ok and value ~= nil then
            KnownClientCheatModules[module_name] = value
            if not ClientCheatModulesLogged then
                log(string.format("CCC module bootstrap via %s: %s", tostring(mode), tostring(module_name)))
                log_client_cheat_module_summary(module_name, value)
            end
        elseif not ClientCheatModulesLogged then
            log(string.format(
                "CCC module bootstrap failed via %s: %s => %s",
                tostring(mode),
                tostring(module_name),
                tostring(value)
            ))
        end
    end

    ClientCheatModulesLogged = true
    return KnownClientCheatModules
end

local function get_function_source(func)
    if type(func) ~= "function" or not debug or not debug.getinfo then
        return nil
    end

    local ok, info = pcall(debug.getinfo, func, "S")
    if not ok or type(info) ~= "table" then
        return nil
    end
    return tostring(info.source or "")
end

local function function_mentions_client_cheat(func)
    return path_mentions_client_cheat(get_function_source(func))
end

local function summarize_hidden_candidate(candidate)
    if type(candidate) ~= "table" then
        return 0, {}, 0, {}, 0, {}, 0
    end

    local seen = {}
    local direct_hits = {}
    local indexed_hits = {}
    local descriptor_hits = {}
    local total_entries = 0

    for _, command_name in ipairs(HiddenCommandNames) do
        local direct_value = rawget(candidate, command_name)
        if has_hidden_callable_shape(direct_value) then
            append_unique(direct_hits, seen, command_name)
        end

        local ok, indexed_value = pcall(function()
            return candidate[command_name]
        end)
        if ok and indexed_value ~= direct_value and has_hidden_callable_shape(indexed_value) then
            append_unique(indexed_hits, seen, command_name)
        end
    end

    for key, value in next, candidate do
        total_entries = total_entries + 1

        local normalized_key = normalize_hidden_name(key)
        if normalized_key and HiddenCommandLookup[normalized_key] and has_hidden_callable_shape(value) then
            append_unique(direct_hits, seen, normalized_key)
        end

        local descriptor_name = extract_hidden_descriptor_name(value)
        if descriptor_name and HiddenCommandLookup[descriptor_name] and has_hidden_callable_shape(value) then
            append_unique(descriptor_hits, seen, descriptor_name)
        end

    end

    return #direct_hits, direct_hits, #indexed_hits, indexed_hits, #descriptor_hits, descriptor_hits, total_entries
end

local function looks_like_hidden_registry(candidate)
    if candidate == HiddenCommandNames or candidate == HiddenCommandLookup then
        return false, {}, {}, {}
    end

    local direct_count, direct_hits, indexed_count, indexed_hits, descriptor_count, descriptor_hits =
        summarize_hidden_candidate(candidate)
    local total_count = direct_count + indexed_count + descriptor_count
    if direct_count >= 4 then
        return true, direct_hits, indexed_hits, descriptor_hits
    end
    if indexed_count >= 4 then
        return true, direct_hits, indexed_hits, descriptor_hits
    end
    if direct_count + indexed_count >= 2 and total_count >= 5 then
        return true, direct_hits, indexed_hits, descriptor_hits
    end
    if descriptor_count >= 4 then
        return true, direct_hits, indexed_hits, descriptor_hits
    end
    return false, direct_hits, indexed_hits, descriptor_hits
end

local function remember_hidden_candidate(candidates, path, candidate, direct_hits, indexed_hits, descriptor_hits)
    local score = (#direct_hits * 12) + (#indexed_hits * 10) + (#descriptor_hits * 4)
    if path_mentions_client_cheat(path) then
        score = score + 40
    end
    if score < 2 then
        return
    end

    for index, existing in ipairs(candidates) do
        if existing.path == path then
            if existing.score >= score then
                return
            end
            table.remove(candidates, index)
            break
        end
    end

    table.insert(candidates, {
        score = score,
        path = path,
        direct_hits = direct_hits,
        indexed_hits = indexed_hits,
        descriptor_hits = descriptor_hits,
        description = describe_hidden_entry(candidate),
    })
    table.sort(candidates, function(left, right)
        if left.score == right.score then
            return left.path < right.path
        end
        return left.score > right.score
    end)
    while #candidates > 8 do
        table.remove(candidates)
    end
end

local function try_get_debug_registry()
    if not debug or not debug.getregistry then
        return nil
    end
    local ok, registry = pcall(debug.getregistry)
    if ok and type(registry) == "table" then
        return registry
    end
    return nil
end

local function seed_hidden_client_cheat_roots(queue, seen_tables, seen_functions)
    local seeded = 0

    local known_modules = load_known_client_cheat_modules()
    if type(known_modules) == "table" then
        for _, module_name in ipairs(KnownClientCheatModuleNames) do
            local value = known_modules[module_name]
            if type(value) == "table" then
                enqueue_hidden_table(queue, seen_tables, "ccc.module." .. module_name, value, 0)
                enqueue_hidden_metatable(queue, seen_tables, "ccc.module." .. module_name, value, 1)
                seeded = seeded + 1
            elseif type(value) == "function" then
                enqueue_hidden_function(queue, seen_functions, "ccc.module." .. module_name, value, 0)
                seeded = seeded + 1
            end
        end
    end

    if package and type(package.loaded) == "table" then
        for key, value in next, package.loaded do
            local key_text = tostring(key)
            if path_mentions_client_cheat(key_text) then
                if type(value) == "table" then
                    enqueue_hidden_table(queue, seen_tables, "package.loaded." .. key_text, value, 0)
                    enqueue_hidden_metatable(queue, seen_tables, "package.loaded." .. key_text, value, 1)
                    seeded = seeded + 1
                elseif type(value) == "function" then
                    enqueue_hidden_function(queue, seen_functions, "package.loaded." .. key_text, value, 0)
                    seeded = seeded + 1
                end
            elseif type(value) == "function" and function_mentions_client_cheat(value) then
                enqueue_hidden_function(queue, seen_functions, "package.loaded[" .. key_text .. "]<function>", value, 0)
                seeded = seeded + 1
            end
        end
    end

    local registry = try_get_debug_registry()
    if type(registry) == "table" then
        local registry_count = 0
        for key, value in next, registry do
            if type(value) == "function" and function_mentions_client_cheat(value) then
                enqueue_hidden_function(
                    queue,
                    seen_functions,
                    "debug.getregistry()[" .. tostring(key) .. "]<client_cheat_function>",
                    value,
                    0
                )
                registry_count = registry_count + 1
            elseif type(value) == "table" and path_mentions_client_cheat(key) then
                enqueue_hidden_table(
                    queue,
                    seen_tables,
                    "debug.getregistry()[" .. tostring(key) .. "]<client_cheat_table>",
                    value,
                    0
                )
                enqueue_hidden_metatable(
                    queue,
                    seen_tables,
                    "debug.getregistry()[" .. tostring(key) .. "]<client_cheat_table>",
                    value,
                    1
                )
                registry_count = registry_count + 1
            end

            if registry_count >= 256 then
                break
            end
        end
        seeded = seeded + registry_count
    end

    return seeded
end

local function try_get_metatable(value)
    local getter = nil
    if debug and debug.getmetatable then
        getter = debug.getmetatable
    elseif getmetatable then
        getter = getmetatable
    end
    if not getter then
        return nil
    end

    local ok, meta = pcall(getter, value)
    if ok and type(meta) == "table" then
        return meta
    end
    return nil
end

local function safe_param_get(param)
    if param == nil then
        return nil
    end

    local ok, value = pcall(function()
        return param:get()
    end)
    if ok then
        return value
    end
    return param
end

local function safe_param_set(param, value)
    if param == nil then
        return false
    end

    local ok = pcall(function()
        param:set(value)
    end)
    return ok
end

local function text_like_to_string(value)
    if type(value) == "string" then
        return value
    end
    if value == nil or type(value) ~= "userdata" then
        return nil
    end

    local ok_type, value_type = pcall(function()
        return value:type()
    end)
    if not ok_type then
        return nil
    end
    if value_type ~= "FString"
        and value_type ~= "FText"
        and value_type ~= "FName"
        and value_type ~= "FUtf8String"
        and value_type ~= "FAnsiString"
    then
        return nil
    end

    local ok_text, text = pcall(function()
        return value:ToString()
    end)
    if ok_text and type(text) == "string" then
        return text
    end
    return nil
end

local function blank_text_like(value)
    if type(value) == "string" then
        return ""
    end
    if value == nil or type(value) ~= "userdata" then
        return nil
    end

    local ok_type, value_type = pcall(function()
        return value:type()
    end)
    if not ok_type then
        return nil
    end

    if value_type == "FString"
        or value_type == "FUtf8String"
        or value_type == "FAnsiString"
    then
        local ok_clear = pcall(function()
            if value.Clear then
                value:Clear()
            elseif value.Empty then
                value:Empty()
            end
        end)
        if ok_clear then
            return value
        end
        return ""
    end
    if value_type == "FText" then
        local ok_text, empty_text = pcall(FText, "")
        if ok_text then
            return empty_text
        end
        return nil
    end
    if value_type == "FName" then
        local ok_name, empty_name = pcall(FName, "")
        if ok_name then
            return empty_name
        end
        return nil
    end

    return nil
end

local function extract_chat_text_candidate(payload)
    local direct_text = text_like_to_string(payload)
    if direct_text ~= nil then
        return direct_text, "direct"
    end

    if payload == nil or (type(payload) ~= "table" and type(payload) ~= "userdata") then
        return nil, nil
    end

    for _, field in ipairs({
        "Message",
        "Text",
        "Content",
        "Body",
        "ChatText",
        "DisplayText",
        "RawText",
    }) do
        local ok_field, field_value = pcall(function()
            return payload[field]
        end)
        if ok_field then
            local field_text = text_like_to_string(field_value)
            if field_text ~= nil then
                return field_text, field
            end
        end
    end

    return nil, nil
end

local function suppress_chat_param_message(param)
    local payload = safe_param_get(param)
    local message_text, mode = extract_chat_text_candidate(payload)
    if not message_text or not starts_with_hidden_chat_command(message_text) then
        return false, message_text, mode or "not_hidden"
    end

    local replacement = blank_text_like(payload)
    if replacement ~= nil and safe_param_set(param, replacement) then
        return true, message_text, "param_set:" .. tostring(mode)
    end

    if payload ~= nil and (type(payload) == "table" or type(payload) == "userdata") then
        for _, field in ipairs({
            "Message",
            "Text",
            "Content",
            "Body",
            "ChatText",
            "DisplayText",
            "RawText",
        }) do
            local ok_field, field_value = pcall(function()
                return payload[field]
            end)
            if ok_field then
                local field_text = text_like_to_string(field_value)
                if field_text ~= nil then
                    local blank_value = blank_text_like(field_value)
                    if blank_value == nil then
                        blank_value = ""
                    end
                    local ok_set = pcall(function()
                        payload[field] = blank_value
                    end)
                    if ok_set then
                        pcall(function()
                            param:set(payload)
                        end)
                        return true, message_text, "field_set:" .. field
                    end
                end
            end
        end
    end

    return false, message_text, "unable_to_blank"
end

local function enqueue_hidden_table(queue, seen_tables, path, value, depth)
    if type(value) ~= "table" or seen_tables[value] then
        return
    end
    seen_tables[value] = true
    table.insert(queue, {
        kind = "table",
        path = path,
        value = value,
        depth = depth,
    })
end

local function enqueue_hidden_function(queue, seen_functions, path, value, depth)
    if type(value) ~= "function" or seen_functions[value] then
        return
    end
    seen_functions[value] = true
    table.insert(queue, {
        kind = "function",
        path = path,
        value = value,
        depth = depth,
    })
end

local function enqueue_hidden_metatable(queue, seen_tables, path, value, depth)
    local meta = try_get_metatable(value)
    if type(meta) == "table" then
        enqueue_hidden_table(queue, seen_tables, string.format("%s<metatable>", path), meta, depth)
    end
end

local function enqueue_hidden_upvalues(queue, seen_tables, seen_functions, path, func, depth)
    if type(func) ~= "function" or not debug or not debug.getupvalue then
        return
    end

    for index = 1, 24 do
        local name, value = debug.getupvalue(func, index)
        if name == nil then
            break
        end
        local child_path = string.format("%s<upvalue:%s>", path, tostring(name))
        if type(value) == "table" then
            enqueue_hidden_table(queue, seen_tables, child_path, value, depth)
        elseif type(value) == "function" then
            enqueue_hidden_function(queue, seen_functions, child_path, value, depth)
        end
    end
end

local function hidden_child_path(path, key)
    local key_text = tostring(key)
    local child_path = string.format("%s[%s]", path, key_text)
    if type(key) == "string" and key:match("^[%w_]+$") then
        child_path = path .. "." .. key
    end
    return child_path
end

local function discover_hidden_registry()
    if HiddenCommandRegistry ~= nil then
        HiddenRegistryReady = true
        return HiddenCommandRegistry, HiddenCommandRegistryPath
    end

    local known_modules = load_known_client_cheat_modules()
    local known_handler = type(known_modules) == "table" and known_modules["core.handler"] or nil
    if type(known_handler) == "table" then
        local matched, direct_hits, indexed_hits, descriptor_hits = looks_like_hidden_registry(known_handler)
        if matched then
            HiddenCommandRegistry = known_handler
            HiddenCommandRegistryPath = "ccc.module.core.handler"
            HiddenRegistryReady = true
            log(string.format(
                "Hidden registry found: %s (direct=%s indexed=%s descriptor=%s)",
                HiddenCommandRegistryPath,
                join_hidden_hits(direct_hits),
                join_hidden_hits(indexed_hits),
                join_hidden_hits(descriptor_hits)
            ))
            for _, command_name in ipairs(HiddenCommandNames) do
                local entry = rawget(known_handler, command_name)
                if entry ~= nil then
                    log(string.format("  %s => %s", command_name, describe_hidden_entry(entry)))
                end
            end
            return HiddenCommandRegistry, HiddenCommandRegistryPath
        end
    end

    local max_depth = 8
    local max_nodes = 16384
    local queue = {}
    local seen_tables = {}
    local seen_functions = {}
    local best_candidates = {}
    enqueue_hidden_table(queue, seen_tables, "package.loaded", package.loaded, 0)
    enqueue_hidden_table(queue, seen_tables, "_G", _G, 0)
    enqueue_hidden_metatable(queue, seen_tables, "package.loaded", package.loaded, 1)
    enqueue_hidden_metatable(queue, seen_tables, "_G", _G, 1)

    local debug_registry = try_get_debug_registry()
    if debug_registry then
        enqueue_hidden_table(queue, seen_tables, "debug.getregistry()", debug_registry, 0)
        enqueue_hidden_metatable(queue, seen_tables, "debug.getregistry()", debug_registry, 1)
    end
    local targeted_roots = seed_hidden_client_cheat_roots(queue, seen_tables, seen_functions)
    if targeted_roots > 0 then
        log(string.format("Seeded %d ClientCheatCommands-specific discovery roots.", targeted_roots))
    end

    local index = 1
    while index <= #queue and index <= max_nodes do
        local node = queue[index]
        index = index + 1

        if node.kind == "table" then
            local matched, direct_hits, indexed_hits, descriptor_hits = looks_like_hidden_registry(node.value)
            if matched then
                HiddenCommandRegistry = node.value
                HiddenCommandRegistryPath = node.path
                HiddenRegistryReady = true
                log(string.format(
                    "Hidden registry found: %s (direct=%s indexed=%s descriptor=%s)",
                    node.path,
                    join_hidden_hits(direct_hits),
                    join_hidden_hits(indexed_hits),
                    join_hidden_hits(descriptor_hits)
                ))
                for _, command_name in ipairs(HiddenCommandNames) do
                    local entry = rawget(node.value, command_name)
                    if entry ~= nil then
                        log(string.format("  %s => %s", command_name, describe_hidden_entry(entry)))
                    end
                end
                return HiddenCommandRegistry, HiddenCommandRegistryPath
            end

            remember_hidden_candidate(
                best_candidates,
                node.path,
                node.value,
                direct_hits,
                indexed_hits,
                descriptor_hits
            )

            if node.depth < max_depth then
                enqueue_hidden_metatable(queue, seen_tables, node.path, node.value, node.depth + 1)
                for key, value in next, node.value do
                    local child_path = hidden_child_path(node.path, key)

                    if type(key) == "table" then
                        enqueue_hidden_table(queue, seen_tables, child_path .. "<key>", key, node.depth + 1)
                    elseif type(key) == "function" then
                        enqueue_hidden_function(queue, seen_functions, child_path .. "<key>", key, node.depth + 1)
                    end

                    if type(value) == "table" then
                        enqueue_hidden_table(queue, seen_tables, child_path, value, node.depth + 1)
                    elseif type(value) == "function" then
                        enqueue_hidden_function(queue, seen_functions, child_path, value, node.depth + 1)
                    end
                end
            end
        elseif node.kind == "function" and node.depth < max_depth then
            enqueue_hidden_metatable(queue, seen_tables, node.path, node.value, node.depth + 1)
            enqueue_hidden_upvalues(queue, seen_tables, seen_functions, node.path, node.value, node.depth + 1)
        end
    end

    HiddenRegistryReady = false
    if index > max_nodes then
        log(string.format("Hidden registry discovery hit node cap %d.", max_nodes))
    end
    if #best_candidates > 0 then
        log("Hidden registry discovery failed. Top candidates:")
        for _, candidate in ipairs(best_candidates) do
            log(string.format(
                "  score=%d path=%s direct=%s indexed=%s descriptor=%s => %s",
                candidate.score,
                candidate.path,
                join_hidden_hits(candidate.direct_hits),
                join_hidden_hits(candidate.indexed_hits),
                join_hidden_hits(candidate.descriptor_hits),
                candidate.description
            ))
        end
        return nil, nil
    end

    log("Hidden registry discovery failed.")
    return nil, nil
end

local function parse_hidden_command_line(line)
    local normalized = trim(line)
    if normalized == "" then
        return nil
    end

    while normalized:sub(1, 1) == "/" do
        normalized = trim(normalized:sub(2))
    end
    if normalized:sub(1, 2) == "@!" then
        normalized = normalized:sub(3)
    elseif normalized:sub(1, 1) == "!" or normalized:sub(1, 1) == "@" then
        normalized = normalized:sub(2)
    end

    normalized = trim(normalized)
    if normalized == "" then
        return nil
    end

    local command_name, args_text = normalized:match("^(%S+)%s*(.-)%s*$")
    if not command_name or command_name == "" then
        return nil
    end

    local args = {}
    if args_text and args_text ~= "" then
        for token in args_text:gmatch("%S+") do
            table.insert(args, token)
        end
    end

    return string.lower(command_name), args_text or "", args
end

local function build_hidden_command_text(command_name, args_text)
    local normalized_args = trim(args_text or "")
    if normalized_args ~= "" then
        return string.format("@!%s %s", tostring(command_name), normalized_args)
    end
    return string.format("@!%s", tostring(command_name))
end

local function collect_hidden_callables(entry, label)
    local callables = {}
    local seen = {}

    local function add_callable(func, func_label, self_arg)
        if type(func) ~= "function" then
            return
        end
        local owner_key = self_arg or false
        seen[func] = seen[func] or {}
        if seen[func][owner_key] then
            return
        end
        seen[func][owner_key] = true
        table.insert(callables, {
            func = func,
            label = func_label,
            self_arg = self_arg,
        })
    end

    local function add_metacall(value, value_label)
        local meta = try_get_metatable(value)
        if type(meta) ~= "table" then
            return
        end
        local metacall = rawget(meta, "__call")
        if type(metacall) == "function" then
            add_callable(metacall, value_label .. ".__call", value)
        end
    end

    if type(entry) == "function" then
        add_callable(entry, label)
        return callables
    end
    if type(entry) ~= "table" then
        return callables
    end

    add_metacall(entry, label)
    for key, value in next, entry do
        if type(value) == "function" then
            add_callable(value, string.format("%s.%s", label, tostring(key)), entry)
        end
    end
    for key, value in next, entry do
        if type(value) == "table" then
            local nested_label = string.format("%s.%s", label, tostring(key))
            add_metacall(value, nested_label)
            for nested_key, nested_value in next, value do
                if type(nested_value) == "function" then
                    add_callable(
                        nested_value,
                        string.format("%s.%s", nested_label, tostring(nested_key)),
                        value
                    )
                end
            end
        end
    end

    return callables
end

local function invoke_hidden_callable(callable, command_name, args_text, args)
    local unpack_args = table.unpack or unpack
    local attempts = {}

    local function add_attempt(label, fn)
        table.insert(attempts, {
            label = label,
            fn = fn,
        })
    end

    local function add_attempts(prefix, invoke)
        if #args == 0 then
            add_attempt(prefix .. "no_args", function()
                return invoke()
            end)
            add_attempt(prefix .. "empty_args_table", function()
                return invoke({})
            end)
            add_attempt(prefix .. "empty_args_text", function()
                return invoke("")
            end)
            add_attempt(prefix .. "command_and_empty_table", function()
                return invoke(command_name, {})
            end)
            add_attempt(prefix .. "command_only", function()
                return invoke(command_name)
            end)
            add_attempt(prefix .. "command_and_empty_text", function()
                return invoke(command_name, "")
            end)
        else
            add_attempt(prefix .. "args_table", function()
                return invoke(args)
            end)
            add_attempt(prefix .. "args_text", function()
                return invoke(args_text)
            end)
            if unpack_args then
                add_attempt(prefix .. "unpacked_args", function()
                    return invoke(unpack_args(args))
                end)
            end
            add_attempt(prefix .. "command_and_args_table", function()
                return invoke(command_name, args)
            end)
            add_attempt(prefix .. "command_and_args_text", function()
                return invoke(command_name, args_text)
            end)
            add_attempt(prefix .. "command_args_text_and_table", function()
                return invoke(command_name, args_text, args)
            end)
            if unpack_args then
                add_attempt(prefix .. "command_and_unpacked_args", function()
                    return invoke(command_name, unpack_args(args))
                end)
            end
        end
    end

    if callable.self_arg ~= nil then
        add_attempts("self_", function(...)
            return callable.func(callable.self_arg, ...)
        end)
    end
    add_attempts("", function(...)
        return callable.func(...)
    end)

    local last_error = "no_attempts"
    for _, attempt in ipairs(attempts) do
        local ok, result = pcall(attempt.fn)
        if ok and result ~= false then
            log(string.format(
                "Hidden command '%s' dispatched via %s / %s",
                command_name,
                callable.label,
                attempt.label
            ))
            return true, nil
        end
        last_error = ok and "returned false" or tostring(result)
    end

    return false, last_error
end

local function resolve_hidden_entry(registry, command_name)
    local entry = rawget(registry, command_name)
    if entry ~= nil then
        return entry, "direct"
    end

    local ok, indexed_entry = pcall(function()
        return registry[command_name]
    end)
    if ok and indexed_entry ~= nil then
        return indexed_entry, "metatable"
    end

    for key, value in next, registry do
        local normalized_key = normalize_hidden_name(key)
        if normalized_key == command_name then
            return value, string.format("string_key:%s", tostring(key))
        end

        local descriptor_name = extract_hidden_descriptor_name(value)
        if descriptor_name == command_name then
            return value, string.format("descriptor:%s", tostring(key))
        end
    end

    return nil, nil
end

local function execute_hidden_command(command_name, args_text, args)
    local registry = discover_hidden_registry()
    if not registry then
        return false, "registry_missing"
    end

    local entry, resolve_mode = resolve_hidden_entry(registry, command_name)
    if entry == nil then
        return false, "command_not_registered"
    end
    if resolve_mode ~= "direct" then
        log(string.format(
            "Hidden command '%s' resolved via %s at %s",
            command_name,
            tostring(resolve_mode),
            tostring(HiddenCommandRegistryPath or "<unknown>")
        ))
    end

    local callables = collect_hidden_callables(entry, command_name)
    if #callables == 0 then
        return false, "entry_not_callable"
    end

    local last_error = "call_failed"
    for _, callable in ipairs(callables) do
        local ok, error_message = invoke_hidden_callable(callable, command_name, args_text, args)
        if ok then
            return true, nil
        end
        last_error = error_message or last_error
    end

    return false, last_error
end

local function execute_hidden_via_chat_hook(command_name, args_text)
    local known_modules = load_known_client_cheat_modules()
    local logic = type(known_modules) == "table" and known_modules["core.logic"] or nil
    local chat_hook = type(logic) == "table" and logic.chatHook or nil
    if type(chat_hook) ~= "function" then
        return false, "chat_hook_missing"
    end

    local command_text = build_hidden_command_text(command_name, args_text)
    local controller = get_player_controller()
    local attempts = {
        {
            label = "text_only",
            fn = function()
                return chat_hook(command_text)
            end,
        },
        {
            label = "message_table",
            fn = function()
                return chat_hook({ Message = command_text })
            end,
        },
        {
            label = "controller_and_message_table",
            fn = function()
                return chat_hook(controller, { Message = command_text })
            end,
        },
        {
            label = "nil_and_message_table",
            fn = function()
                return chat_hook(nil, { Message = command_text })
            end,
        },
        {
            label = "controller_and_param_like",
            fn = function()
                local payload = { Message = command_text }
                return chat_hook(controller, {
                    get = function()
                        return payload
                    end,
                    set = function(new_value)
                        payload = new_value
                    end,
                })
            end,
        },
        {
            label = "nil_and_param_like",
            fn = function()
                local payload = { Message = command_text }
                return chat_hook(nil, {
                    get = function()
                        return payload
                    end,
                    set = function(new_value)
                        payload = new_value
                    end,
                })
            end,
        },
    }

    local last_error = "chat_hook_failed"
    for _, attempt in ipairs(attempts) do
        local ok, result = pcall(attempt.fn)
        if ok and result ~= false then
            log(string.format(
                "Hidden command '%s' dispatched via core.logic.chatHook / %s",
                tostring(command_name),
                tostring(attempt.label)
            ))
            return true, nil
        end
        last_error = ok and "returned false" or tostring(result)
    end

    return false, last_error
end

local function run_hidden_commands(request)
    local commands_text = trim(request.commands_text)
    if commands_text == "" then
        return false, "empty_commands"
    end

    local executed = 0
    for line in commands_text:gmatch("[^\r\n]+") do
        local command_name, args_text, args = parse_hidden_command_line(line)
        if command_name ~= nil then
            local ok, error_message = execute_hidden_command(command_name, args_text, args)
            if not ok then
                ok, error_message = execute_hidden_via_chat_hook(command_name, args_text)
            end
            if not ok then
                return false, string.format("%s (%s)", command_name, tostring(error_message))
            end
            executed = executed + 1
        end
    end

    if executed < 1 then
        return false, "no_valid_commands"
    end
    return true, tostring(executed)
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
            '{\n  "player_valid": false,\n  "bridge_version": "%s",\n  "hidden_registry_ready": %s,\n  "chat_suppression_ready": %s\n}\n',
            Version,
            tostring(HiddenRegistryReady),
            tostring(ChatSuppressionReady)
        ))
        handle:close()
        return true
    end

    local location = player:K2_GetActorLocation()
    handle:write(string.format(
        '{\n  "player_valid": true,\n  "bridge_version": "%s",\n  "hidden_registry_ready": %s,\n  "chat_suppression_ready": %s,\n  "position_x": %.3f,\n  "position_y": %.3f,\n  "position_z": %.3f\n}\n',
        Version,
        tostring(HiddenRegistryReady),
        tostring(ChatSuppressionReady),
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
        commands_text = parse_string(text, "commands_text"),
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
    elseif request.action == "run_hidden_commands" then
        local player = get_player()
        if not player:IsValid() then
            log(string.format("Hidden-command request #%d ignored: local player not ready.", request.request_id))
            return
        end

        local ok, detail = run_hidden_commands(request)
        if ok then
            log(string.format(
                "Hidden-command request #%d executed %s command(s).",
                request.request_id,
                tostring(detail)
            ))
        else
            log(string.format(
                "Hidden-command request #%d failed: %s",
                request.request_id,
                tostring(detail)
            ))
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

local function handle_chat_suppression(message_param, phase)
    local hook_ok, hook_error = pcall(function()
        local suppressed, message_text, detail = suppress_chat_param_message(message_param)
        if not message_text or not starts_with_hidden_chat_command(message_text) then
            return
        end

        if not ChatSuppressionProbeLogged then
            ChatSuppressionProbeLogged = true
            log(string.format(
                "Chat suppression probe => phase=%s detail=%s text=%s",
                tostring(phase),
                tostring(detail),
                tostring(message_text)
            ))
        end

        if suppressed then
            log(string.format(
                "Suppressed visible chat command via %s/%s: %s",
                tostring(phase),
                tostring(detail),
                tostring(message_text)
            ))
        else
            log(string.format(
                "Visible chat command suppression failed (%s/%s): %s",
                tostring(phase),
                tostring(detail),
                tostring(message_text)
            ))
        end
    end)
    if not hook_ok then
        log("Chat suppression hook error: " .. tostring(hook_error))
    end
end

do
    local ok, pre_id, post_id = pcall(
        RegisterHook,
        "/Script/Pal.PalUIChat:OnReceivedChat",
        function(context, message_param)
            return
        end,
        function(context, message_param)
            handle_chat_suppression(message_param, "post")
        end
    )

    if ok and pre_id ~= nil then
        ChatSuppressionReady = true
    else
        ChatSuppressionReady = false
        log("Chat suppression hook registration failed: " .. tostring(pre_id))
    end
end

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
    pcall(discover_hidden_registry)
    pcall(write_status)
end)
