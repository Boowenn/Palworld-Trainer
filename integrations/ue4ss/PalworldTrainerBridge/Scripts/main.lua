local UEHelpers = require("UEHelpers")

local ModName = "PalworldTrainerBridge"
local Version = "0.2.0"

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

RegisterConsoleCommandHandler("pt_help", function(full_command, parameters, ar)
    log("Available commands:")
    log("pt_help   - print the available trainer bridge commands")
    log("pt_status - print trainer bridge and player status")
    log("pt_pos    - print the local player coordinates")
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

RegisterKeyBindAsync(Key.F6, { ModifierKey.CONTROL }, function()
    local player = get_player()
    if not player:IsValid() then
        log("CTRL+F6 pressed, but the local player is not ready yet.")
        return
    end

    local location = player:K2_GetActorLocation()
    log("CTRL+F6 => " .. format_vector(location))
end)

RegisterHook("/Script/Engine.PlayerController:ClientRestart", function(self, new_pawn)
    ExecuteInGameThread(function()
        print_status()
    end)
end)

ExecuteInGameThread(function()
    log("Bridge loaded.")
    log("Use the console command pt_help or press CTRL+F6 in-game.")
end)

