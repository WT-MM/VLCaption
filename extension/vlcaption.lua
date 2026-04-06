-- VLCaption - Auto-generate subtitles for VLC
-- https://github.com/WT-MM/VLCaption

local SERVER_HOST = "127.0.0.1"
local SERVER_PORT = 9839
local POLL_MESSAGE = "Click 'Refresh' to check progress..."

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
local srt_path_pending = nil

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
    if not item then return nil, "No media is currently playing." end
    local uri = item:uri()
    if not uri then return nil, "Could not get media URI." end
    if not uri:match("^file://") then
        return nil, "Only local files are supported (got: " .. uri:sub(1, 30) .. "...)"
    end
    return decode_file_uri(uri), nil
end

---------------------------------------------------------------------
-- HTTP helper (raw TCP via vlc.net)
---------------------------------------------------------------------

local function http_request(method, path, body)
    local fd = vlc.net.connect_tcp(SERVER_HOST, SERVER_PORT)
    if not fd or fd < 0 then
        return nil, "Could not connect to VLCaption server."
    end

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
        return nil, "Empty response from server."
    end

    -- Split headers and body
    local _, _, resp_body = response:find("\r\n\r\n(.*)")
    return resp_body or response, nil
end

local function server_is_running()
    local body, err = http_request("GET", "/health", nil)
    if err then return false end
    return body and body:find('"ok"') ~= nil
end

---------------------------------------------------------------------
-- Server auto-launch
---------------------------------------------------------------------

local function ensure_server()
    if server_is_running() then return true end

    -- Try to launch the server in the background
    local cmd
    if package.config:sub(1, 1) == "\\" then
        -- Windows
        cmd = 'start /b python -m vlcaption >nul 2>&1'
    else
        -- macOS / Linux
        cmd = 'python3 -m vlcaption > /dev/null 2>&1 &'
    end

    vlc.msg.info("[VLCaption] Starting server: " .. cmd)
    os.execute(cmd)

    -- Wait up to 8 seconds for the server to start
    for i = 1, 16 do
        vlc.misc.mwait(vlc.misc.mdate() + 500000) -- 0.5 second
        if server_is_running() then
            vlc.msg.info("[VLCaption] Server started after " .. (i * 0.5) .. "s")
            return true
        end
    end

    return false
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

    status_label:set_text("Starting server...")
    dlg:update()

    -- Ensure server is running
    if not ensure_server() then
        status_label:set_text("Error: Could not start VLCaption server.\n"
            .. "Install with: pip install vlcaption")
        return
    end

    -- Get selected model
    local model_choices = {"tiny", "base", "small", "medium", "large-v3"}
    local model_idx = model_dropdown:get_value()
    local model = model_choices[model_idx] or "base"

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
        status_label:set_text("Server is not running.")
        return
    end

    local resp, err = http_request("GET", "/progress", nil)
    if err then
        status_label:set_text("Error: " .. err)
        return
    end

    local status = json_value(resp, "status")

    if status == "idle" then
        status_label:set_text("Ready. No transcription in progress.")
    elseif status == "transcribing" then
        local pct = json_value(resp, "percent") or 0
        status_label:set_text("Transcribing... " .. pct .. "% complete.\n" .. POLL_MESSAGE)
    elseif status == "complete" then
        local srt = json_value(resp, "srt_path")
        local lang = json_value(resp, "language") or "?"
        if srt then
            status_label:set_text("Done! Language: " .. lang .. "\nLoading subtitles...")
            dlg:update()
            vlc.input.add_subtitle(srt)
            status_label:set_text("Subtitles loaded! (" .. lang .. ")\n" .. srt)
        else
            status_label:set_text("Complete, but no SRT path returned.")
        end
    elseif status == "error" then
        local msg = json_value(resp, "message") or "Unknown error"
        status_label:set_text("Error: " .. msg)
    else
        status_label:set_text("Unknown status: " .. (status or "nil"))
    end
end

---------------------------------------------------------------------
-- VLC extension lifecycle
---------------------------------------------------------------------

function activate()
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
end

function deactivate()
    -- Try to shut down the server gracefully
    pcall(function()
        http_request("POST", "/shutdown", nil)
    end)

    if dlg then
        dlg:hide()
    end
    dlg = nil
end

function close()
    deactivate()
end
