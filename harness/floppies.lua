-- Hot-swaps the pcmx2 floppy on request: polls the control file named by FLCTL
-- ("unload" or an image path) and logs each change to FLCTL .. ".log".
local ctl = os.getenv("FLCTL")
local img = manager.machine.images[":slot1:storager:floppy0:525qd"]
local logf = io.open(ctl .. ".log", "a")
local function log(s)
	logf:write(string.format("t=%.3f %s\n", manager.machine.time:as_double(), s))
	logf:flush()
end
log("floppy control ready, loaded=" .. tostring(img.filename))
local last = nil
CO = coroutine.create(function()
	while true do
		emu.wait(0.5)
		local f = io.open(ctl, "r")
		if f then
			local c = f:read("*l") or ""
			f:close()
			if c ~= "" and c ~= last then
				last = c
				if c == "unload" then
					img:unload()
					log("unloaded")
				else
					local ok, err = pcall(function() return img:load(c) end)
					log("load " .. c .. " -> " .. tostring(ok) .. " " .. tostring(err) .. " now=" .. tostring(img.filename))
				end
			end
		end
	end
end)
coroutine.resume(CO)
