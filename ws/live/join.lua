local room = ARGV[1]
local limit = tonumber(ARGV[2])

local count = tonumber(redis.call("GET", room) or "0")
if (count < limit) then
    redis.call("INCRBY", room, 1)
    return count + 1
else
    return 0
end