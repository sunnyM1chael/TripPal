local stockKey = KEYS[1]
local seckillUserKey = KEYS[2]
local traceLogKey = KEYS[3]
local reservationOwnerKey = KEYS[4]
local compensatedOrderKey = KEYS[5]
local voucherId = ARGV[1]
local userId = (ARGV[2])
local orderId = ARGV[3]
local seckillVoucherOrderOperate = tonumber(ARGV[4])
local traceId = ARGV[5]
local logType = ARGV[6]
local beforeQty = tonumber(ARGV[7])
local changeQty = tonumber(ARGV[8])
local afterQty = tonumber(ARGV[9])
-- Redis 已完成而数据库尚未写终态时，重试不能重复补偿或生成新流水。
if redis.call('hexists', compensatedOrderKey, orderId) == 1 then
    return 0
end
local reservationOwner = redis.call('hget', reservationOwnerKey, userId)
if seckillVoucherOrderOperate == 1
    and redis.call('sismember', seckillUserKey, userId) == 1
    and not reservationOwner then
    -- 历史购买标记没有订单归属，保留待补偿状态，人工核对后补齐 owner 再重试。
    return -2
end
redis.call('del', stockKey)
if seckillVoucherOrderOperate == 1 then
    -- 旧订单的补偿不得删除用户新订单的购买资格。
    -- 无 owner 的历史数据保守保留，交给人工核对，不猜测所属订单。
    if reservationOwner == orderId then
        redis.call('srem', seckillUserKey, userId)
        redis.call('hdel', reservationOwnerKey, userId)
    end
end
local timeArr = redis.call('TIME')
local nowMillis = tonumber(timeArr[1]) * 1000 + math.floor(tonumber(timeArr[2]) / 1000)
local logEntry = cjson.encode({
    logType = logType,
    ts = nowMillis,
    orderId = orderId,
    traceId = traceId,
    userId = userId,
    voucherId = voucherId,
    beforeQty = beforeQty,
    changeQty = changeQty,
    afterQty = afterQty
})
redis.call('hset', traceLogKey, traceId, logEntry)
redis.call('hset', compensatedOrderKey, orderId, traceId)
return 0
