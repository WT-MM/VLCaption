-- VLCaption - Auto-generate subtitles for VLC
-- https://github.com/WT-MM/VLCaption
--
-- Debug logs visible in VLC > Tools > Messages (set verbosity to 2)

local SERVER_HOST = "127.0.0.1"
local SERVER_PORT = 9839
local SERVER_URL = "http://" .. SERVER_HOST .. ":" .. SERVER_PORT
local POLL_MESSAGE = "Click 'Refresh' to check progress..."

-- Path to the launcher script created by install.sh
local LAUNCHER_PATH = nil

local function get_launcher_path()
    if LAUNCHER_PATH then return LAUNCHER_PATH end
    local home = os.getenv("HOME")
        or os.getenv("USERPROFILE")
        or (os.getenv("HOMEDRIVE") or "" ) .. (os.getenv("HOMEPATH") or "")
    if home and #home > 0 then
        LAUNCHER_PATH = home .. "/.config/vlcaption/launch-server.sh"
    end
    return LAUNCHER_PATH
end

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
        capabilities = { "input-listener" }
    }
end

-- Input-listener stub. Required because we declare the capability so that
-- the extension reliably appears in VLC's menu on all platforms.
function input_changed()
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
-- HTTP helper (via curl + io.popen)
--
-- vlc.net is not officially exposed to the *extension* lua context in
-- VLC 3, so calling vlc.net.connect_tcp from a button callback fails
-- silently. curl is available on every supported platform and io.popen
-- is part of the standard lua library that extensions get.
---------------------------------------------------------------------

local function shell_quote(s)
    -- POSIX-safe single-quote wrap. Replaces ' with '\''.
    return "'" .. tostring(s):gsub("'", "'\\''") .. "'"
end

local function http_request(method, path, body)
    log_dbg("HTTP " .. method .. " " .. path)
    local url = SERVER_URL .. path
    -- Keep well under VLC's ~10s extension watchdog, which offers to kill
    -- any extension whose callback blocks that long.
    local cmd = "curl -sS --max-time 5 -X " .. method
        .. " -H " .. shell_quote("Content-Type: application/json")
    if body then
        cmd = cmd .. " --data-binary " .. shell_quote(body)
    end
    cmd = cmd .. " " .. shell_quote(url) .. " 2>/dev/null"

    local pipe = io.popen(cmd, "r")
    if not pipe then
        log_dbg("io.popen failed")
        return nil, "Could not run curl. Is it installed?"
    end
    local response = pipe:read("*a") or ""
    pipe:close()

    if #response == 0 then
        log_dbg("Empty response from curl (server probably not running)")
        return nil, "Could not connect to VLCaption server."
    end
    log_dbg("Response body: " .. response:sub(1, 200))
    return response, nil
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
    local launcher = get_launcher_path()
    if not launcher then
        log_err("Could not determine HOME directory")
        return false, "Could not determine HOME directory.\nSet HOME env var or run install.sh."
    end
    if not file_exists(launcher) then
        log_err("Launcher not found: " .. launcher)
        return false, "Launcher not found at: " .. launcher
            .. "\nRun install.sh to create it."
    end

    -- Launch server fully detached so VLC isn't waiting on it.
    -- nohup + redirected stdin/stdout/stderr + & yields a daemonized
    -- child that survives even if VLC's foreground shell exits.
    local cmd = "nohup " .. shell_quote(launcher)
        .. " </dev/null >/dev/null 2>&1 &"
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
    local model_choices = {"auto", "parakeet", "whisper-turbo", "whisper-base", "whisper-large-v3"}
    local model_idx = model_dropdown:get_value()
    local model = model_choices[model_idx] or "auto"
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

    status_label:set_text("Transcribing... subtitles will load automatically when done.\n" .. POLL_MESSAGE)
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
    elseif status == "loading_model" then
        status_label:set_text("Loading transcription model (downloads on first use)...\n" .. POLL_MESSAGE)
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
            -- Second arg selects the track; without it the subtitles are
            -- added but stay disabled.
            vlc.input.add_subtitle(srt, true)
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
    -- Ids index into model_choices in do_generate; first entry is default.
    model_dropdown:add_value("auto (best available)", 1)
    model_dropdown:add_value("parakeet (fast, accurate)", 2)
    model_dropdown:add_value("whisper turbo (100 languages)", 3)
    model_dropdown:add_value("whisper base (small download)", 4)
    model_dropdown:add_value("whisper large-v3 (slowest)", 5)

    -- Wrap callbacks in pcall so any unexpected error is shown to the
    -- user instead of being silently swallowed by VLC's extension host.
    local function safe(fn)
        return function()
            local ok, err = pcall(fn)
            if not ok then
                log_err("Callback error: " .. tostring(err))
                if status_label then
                    status_label:set_text("Internal error: " .. tostring(err))
                end
            end
        end
    end

    dlg:add_button("Generate Subtitles", safe(do_generate), 1, 2, 2, 1)
    dlg:add_button("Refresh", safe(do_refresh), 3, 2, 1, 1)

    status_label = dlg:add_label("Ready. Play a media file and click 'Generate Subtitles'.", 1, 3, 3, 1)

    dlg:show()
    log_info("Dialog shown")
end

function deactivate()
    log_info("Extension deactivating")
    -- Do NOT shut the server down here: on macOS, VLC deactivates the
    -- extension every time a new media file is opened, which would kill
    -- in-flight transcriptions. The server exits on its own 30-minute
    -- idle timer instead.

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
