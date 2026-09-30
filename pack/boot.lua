-- PC-MX2 / SINIX V2.0 boot helper, run by SINIX.bat through -autoboot_script.
-- Watches the 97801 terminal screen: runs unthrottled while the system boots, answers the
-- boot-time date question (today's day and time, year 1986: SINIX V2.0 reads a two-digit year
-- and 26 would be 1926, before the Unix epoch), and returns to real speed at the login prompt.
-- Driven by a frame notifier (no coroutine), so nothing is left pending when MAME exits.
local avdc
for tag, dev in pairs(manager.machine.devices) do
	if tag:find("avdc", 1, true) then avdc = dev end
end
if not avdc then return end
local ram = avdc.spaces["charram"]
local video = manager.machine.video
local nk = manager.machine.natkeyboard
local gate = os.getenv("PCMX2_GATE")

local function now() return manager.machine.time:as_double() end

local function screen_text()
	local t = {}
	for a = 0, 0x3fff do
		local c = ram:read_u8(a)
		t[#t + 1] = (c >= 32 and c < 127) and string.char(c) or " "
	end
	return table.concat(t)
end

local function count(s, pat)
	local n, i = 0, 1
	while true do
		local a = s:find(pat, i, true)
		if not a then return n end
		n = n + 1
		i = a + 1
	end
end

local seen_date, seen_login = 0, 0
local next_check = 0
local typing, type_at = "", 0
local gate_exit_at = nil
video.throttled = false

BOOT_HELPER = emu.add_machine_frame_notifier(function()
	local t = now()
	if #typing > 0 and t >= type_at then
		nk:post(typing:sub(1, 1))
		typing = typing:sub(2)
		type_at = t + 0.12
	end
	if gate_exit_at and t >= gate_exit_at then
		gate_exit_at = nil
		manager.machine:exit()
		return
	end
	if t < next_check then return end
	next_check = t + 0.5
	local s = screen_text()
	local d, l = count(s, "Zeit eingeben"), count(s, "Benutzerkennung")
	if d > seen_date then
		video.throttled = false
		typing = "86" .. os.date("%m%d%H%M") .. "\r"
		type_at = t + 1.5
	end
	if l > seen_login then
		video.throttled = true
		if gate then
			-- test hook for the packaging gate only: prove the login prompt, then quit
			video:snapshot()
			local f = io.open(gate, "w")
			if f then f:write("login prompt reached\n"); f:close() end
			gate_exit_at = t + 2
		end
	end
	seen_date, seen_login = d, l
end)
