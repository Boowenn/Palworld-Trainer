local UEHelpers = require("UEHelpers")

local ModName = "PalworldTrainerBridge"
local Version = "0.3.0"
local LastFindQuery = nil

local function log(message)
    print(string.format("[%s] %s\n", ModName, message))
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

local function run_find_query(short_class_name, limit)
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
        }
        return true
    end

    local rows, total = build_rows(objects, limit)
    print_rows(string.format("FindAllOf('%s')", short_class_name), rows, total)

    LastFindQuery = {
        class_name = short_class_name,
        limit = limit,
    }
    return true
end

local function repeat_last_find()
    if not LastFindQuery then
        log("No previous pt_find query is cached yet.")
        return true
    end

    return run_find_query(LastFindQuery.class_name, LastFindQuery.limit)
end

RegisterConsoleCommandHandler("pt_help", function(full_command, parameters, ar)
    log("Available commands:")
    log("pt_help   - print the available trainer bridge commands")
    log("pt_status - print trainer bridge and player status")
    log("pt_pos    - print the local player coordinates")
    log("pt_world  - print the world, level, and replicated player snapshot")
    log("pt_players [limit] - list nearby replicated player pawns")
    log("pt_find <ShortClassName> [limit] - run a generic FindAllOf scan")
    log("pt_repeat - repeat the most recent pt_find query")
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

RegisterConsoleCommandHandler("pt_repeat", function(full_command, parameters, ar)
    return repeat_last_find()
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

RegisterHook("/Script/Engine.PlayerController:ClientRestart", function(self, new_pawn)
    ExecuteInGameThread(function()
        print_status()
    end)
end)

ExecuteInGameThread(function()
    log("Bridge loaded.")
    log("Use pt_help or the hotkeys CTRL+F6 / CTRL+F7 / CTRL+F8 in-game.")
end)
