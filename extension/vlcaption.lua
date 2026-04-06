-- VLCaption - Auto-generate subtitles for VLC
-- https://github.com/WT-MM/VLCaption
--
-- Debug logs visible in VLC > Tools > Messages (set verbosity to 2)

local SERVER_HOST = "127.0.0.1"
local SERVER_PORT = 9839
local POLL_MESSAGE = "Click 'Refresh' to check progress..."

-- Path to the launcher script created by install.sh
local LAUNCHER_PATH = os.getenv("HOME") .. "/.config/vlcaption/launch-server.sh"

-- VLC extension descriptor
function descriptor()
    return {
        title = "VLCaption - Auto Subtitles",
        version = "0.1.0",
        author = "WT-MM",
        url = "https://github.com/WT-MM/VLCaption",
        shortdesc = "VLCaption",
        description = "Auto-generate subtitles using local Whisper models. "
            .. "Requires the VLCaption Python server.",
        capabilities = {}
    }
end

-- State
local dlg = nil
local status_label = nil
local model_dropdown = nil
local server_launched = false

---------------------------------------------------------------------
-- Logging helpers (visible in VLC > Tools > Messages)
---------------------------------------------------------------------

local function log_dbg(msg)
    vlc.msg.dbg("[VLCaption] " .. msg)
end

local function log_info(msg)
    vlc.msg.info("[VLCaption] " .. msg)
end

local function log_err(msg)
    vlc.msg.err("[VLCaption] " .. msg)
end

---------------------------------------------------------------------
-- URI / string helpers
---------------------------------------------------------------------

local function url_decode(str)
    str = str:gsub("%%(%x%x)", function(hex)
        return string.char(tonumber(hex, 16))
    end)
    return str
end

local function decode_file_uri(uri)
    -- Strip file:// prefix (handles file:///path and file://localhost/path)
    local path = uri:gsub("^file://localhost", ""):gsub("^file://", "")
    return url_decode(path)
end

local function get_media_path()
    local item = vlc.input.item()
    if not item then
        log_dbg("No input item")
        return nil, "No media is currently playing."
    end
    local uri = item:uri()
    if not uri then
        log_dbg("No URI on input item")
        return nil, "Could not get media URI."
    end
    log_dbg("Media URI: " .. uri)
    if not uri:match("^file://") then
        return nil, "Only local files are supported (got: " .. uri:sub(1, 30) .. "...)"
    end
    local path = decode_file_uri(uri)
    log_dbg("Decoded path: " .. path)
    return path, nil
end

---------------------------------------------------------------------
-- HTTP helper (raw TCP via vlc.net)
---------------------------------------------------------------------

local function http_request(method, path, body)
    log_dbg("HTTP " .. method .. " " .. path)
    local fd = vlc.net.connect_tcp(SERVER_HOST, SERVER_PORT)
    if not fd or fd < 0 then
        log_dbg("TCP connect failed (fd=" .. tostring(fd) .. ")")
        return nil, "Could not connect to VLCaption server."
    end
    log_dbg("TCP connected (fd=" .. tostring(fd) .. ")")

    local req = method .. " " .. path .. " HTTP/1.1\r\n"
        .. "Host: " .. SERVER_HOST .. ":" .. SERVER_PORT .. "\r\n"
        .. "Connection: close\r\n"

    if body then
        req = req .. "Content-Type: application/json\r\n"
            .. "Content-Length: " .. #body .. "\r\n"
            .. "\r\n" .. body
    else
        req = req .. "\r\n"
    end

    vlc.net.send(fd, req)

    -- Read response (may come in chunks)
    local response = ""
    while true do
        local chunk = vlc.net.recv(fd, 4096)
        if not chunk or #chunk == 0 then break end
        response = response .. chunk
    end

    vlc.net.close(fd)

    if #response == 0 then
        log_dbg("Empty response")
        return nil, "Empty response from server."
    end

    -- Split headers and body
    local _, _, resp_body = response:find("\r\n\r\n(.*)")
    log_dbg("Response body: " .. (resp_body or "nil"):sub(1, 200))
    return resp_body or response, nil
end

local function server_is_running()
    local body, err = http_request("GET", "/health", nil)
    if err then
        log_dbg("Health check failed: " .. err)
        return false
    end
    local ok = body and body:find('"ok"') ~= nil
    log_dbg("Health check: " .. tostring(ok))
    return ok
end

---------------------------------------------------------------------
-- Server auto-launch (non-blocking)
---------------------------------------------------------------------

local function file_exists(path)
    local f = io.open(path, "r")
    if f then
        f:close()
        return true
    end
    return false
end

local function start_server()
    if server_is_running() then
        log_info("Server already running")
        return true
    end

    -- Find the launcher script
    if not file_exists(LAUNCHER_PATH) then
        log_err("Launcher not found: " .. LAUNCHER_PATH)
        return false, "Launcher not found at: " .. LAUNCHER_PATH
            .. "\nRun install.sh to create it."
    end

    -- Launch server in background (non-blocking)
    local cmd = '"' .. LAUNCHER_PATH .. '" > /dev/null 2>&1 &'
    log_info("Launching server: " .. cmd)
    os.execute(cmd)
    server_launched = true

    return nil -- nil means "launched, check back later"
end

---------------------------------------------------------------------
-- JSON value extraction (minimal, no library needed)
---------------------------------------------------------------------

local function json_value(body, key)
    -- Match "key": "value" or "key": number
    local str_val = body:match('"' .. key .. '"%s*:%s*"([^"]*)"')
    if str_val then return str_val end
    local num_val = body:match('"' .. key .. '"%s*:%s*(%d+)')
    if num_val then return tonumber(num_val) end
    return nil
end

---------------------------------------------------------------------
-- Actions
---------------------------------------------------------------------

local function do_generate()
    -- Get current media path
    local path, err = get_media_path()
    if err then
        status_label:set_text("Error: " .. err)
        return
    end

    -- Check/start server (non-blocking)
    local result, start_err = start_server()
    if result == nil then
        -- Server was just launched, not ready yet
        status_label:set_text("Server starting... click 'Generate Subtitles' again in a few seconds.")
        return
    elseif result == false then
        status_label:set_text("Error: " .. (start_err or "Could not start server."))
        return
    end

    -- Server is running, proceed with transcription
    local model_choices = {"tiny", "base", "small", "medium", "large-v3"}
    local model_idx = model_dropdown:get_value()
    local model = model_choices[model_idx] or "base"
    log_info("Generating subtitles with model: " .. model .. " for: " .. path)

    status_label:set_text("Sending transcription request (" .. model .. ")...")
    dlg:update()

    -- Start transcription
    local body_str = '{"file_path": "' .. path:gsub('\\', '\\\\'):gsub('"', '\\"')
        .. '", "model": "' .. model .. '"}'

    local resp, req_err = http_request("POST", "/transcribe", body_str)
    if req_err then
        status_label:set_text("Error: " .. req_err)
        return
    end

    local status = json_value(resp, "status")
    if status == "error" then
        local msg = json_value(resp, "message") or "Unknown error"
        status_label:set_text("Error: " .. msg)
        return
    end

    status_label:set_text("Transcribing... " .. POLL_MESSAGE)
end

local function do_refresh()
    if not server_is_running() then
        if server_launched then
            status_label:set_text("Server is still starting... try again in a moment.")
        else
            status_label:set_text("Server is not running. Click 'Generate Subtitles' to start it.")
        end
        return
    end

    local resp, err = http_request("GET", "/progress", nil)
    if err then
        status_label:set_text("Error: " .. err)
        return
    end

    local status = json_value(resp, "status")
    log_dbg("Progress status: " .. tostring(status))

    if status == "idle" then
        status_label:set_text("Ready. No transcription in progress.")
    elseif status == "transcribing" then
        local pct = json_value(resp, "percent") or 0
        status_label:set_text("Transcribing... " .. pct .. "% complete.\n" .. POLL_MESSAGE)
    elseif status == "complete" then
        local srt = json_value(resp, "srt_path")
        local lang = json_value(resp, "language") or "?"
        if srt then
            log_info("Loading subtitles: " .. srt)
            status_label:set_text("Done! Language: " .. lang .. "\nLoading subtitles...")
            dlg:update()
            vlc.input.add_subtitle(srt)
            status_label:set_text("Subtitles loaded! (" .. lang .. ")\n" .. srt)
        else
            status_label:set_text("Complete, but no SRT path returned.")
        end
    elseif status == "error" then
        local msg = json_value(resp, "message") or "Unknown error"
        log_err("Transcription error: " .. msg)
        status_label:set_text("Error: " .. msg)
    else
        status_label:set_text("Unknown status: " .. (status or "nil"))
    end
end

---------------------------------------------------------------------
-- VLC extension lifecycle
---------------------------------------------------------------------

function activate()
    log_info("Extension activated")
    dlg = vlc.dialog("VLCaption - Auto Subtitles")

    dlg:add_label("<b>Model:</b>", 1, 1, 1, 1)
    model_dropdown = dlg:add_dropdown(2, 1, 2, 1)
    model_dropdown:add_value("base", 2)
    model_dropdown:add_value("tiny", 1)
    model_dropdown:add_value("small", 3)
    model_dropdown:add_value("medium", 4)
    model_dropdown:add_value("large-v3", 5)

    dlg:add_button("Generate Subtitles", do_generate, 1, 2, 2, 1)
    dlg:add_button("Refresh", do_refresh, 3, 2, 1, 1)

    status_label = dlg:add_label("Ready. Play a media file and click 'Generate Subtitles'.", 1, 3, 3, 1)

    dlg:show()
    log_info("Dialog shown")
end

function deactivate()
    log_info("Extension deactivating")
    -- Try to shut down the server gracefully
    pcall(function()
        http_request("POST", "/shutdown", nil)
    end)

    if dlg then
        dlg:hide()
    end
    dlg = nil
    server_launched = false
    log_info("Extension deactivated")
end

function close()
    deactivate()
end
