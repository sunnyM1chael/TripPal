package org.javaup.kafka.consumer;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.TypeReference;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import lombok.extern.slf4j.Slf4j;
import org.javaup.core.RedisKeyManage;
import org.javaup.entity.VoucherOrder;
import org.javaup.entity.VoucherOrderCancellation;
import org.javaup.entity.VoucherReconcileLog;
import org.javaup.enums.BusinessType;
import org.javaup.enums.LogType;
import org.javaup.enums.OrderStatus;
import org.javaup.enums.SeckillVoucherOrderOperate;
import org.javaup.exception.OrderRejectedException;
import org.javaup.kafka.message.SeckillVoucherMessage;
import org.javaup.kafka.redis.RedisVoucherData;
import org.javaup.mapper.VoucherOrderCancellationMapper;
import org.javaup.mapper.VoucherOrderMapper;
import org.javaup.mapper.VoucherReconcileLogMapper;
import org.javaup.message.MessageExtend;
import org.javaup.redis.RedisKeyBuild;
import org.javaup.service.IVoucherOrderService;
import org.javaup.toolkit.SnowflakeIdGenerator;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.context.annotation.Lazy;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDateTime;
import java.util.function.Supplier;

/** 下单、重投、超时和发送失败共用同一业务锁，锁一直持有到事务提交之后。 */
@Slf4j
@Service
public class SeckillOrderProcessor {
    private final IVoucherOrderService orders;
    private final VoucherOrderMapper orderMapper;
    private final VoucherOrderCancellationMapper cancellations;
    private final RedisVoucherData redisVoucherData;
    private final VoucherReconcileLogMapper reconcileLogs;
    private final SnowflakeIdGenerator ids;
    private final RedissonClient redisson;
    private final TransactionTemplate transaction;

    public SeckillOrderProcessor(@Lazy IVoucherOrderService orders, VoucherOrderMapper orderMapper,
            VoucherOrderCancellationMapper cancellations, RedisVoucherData redisVoucherData,
            VoucherReconcileLogMapper reconcileLogs, SnowflakeIdGenerator ids,
            RedissonClient redisson, PlatformTransactionManager transactionManager) {
        this.orders = orders;
        this.orderMapper = orderMapper;
        this.cancellations = cancellations;
        this.redisVoucherData = redisVoucherData;
        this.reconcileLogs = reconcileLogs;
        this.ids = ids;
        this.redisson = redisson;
        this.transaction = new TransactionTemplate(transactionManager);
        this.transaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    public OrderConsumeResult process(MessageExtend<SeckillVoucherMessage> message) {
        return withLock(message, () -> {
            if (existingOrder(message) != null) {
                return OrderConsumeResult.ALREADY_PROCESSED;
            }
            VoucherOrderCancellation cancellation = findCancellation(message.getMessageBody());
            if (cancellation != null) {
                return completeCancellation(message, cancellation);
            }
            // 查重优先于超时：成功订单的迟到消息不能触发回滚。
            if (System.currentTimeMillis() - message.getProducerTime().getTime()
                    > SeckillVoucherConsumer.MESSAGE_DELAY_TIME) {
                return cancelLocked(message, "TIMEOUT");
            }
            try {
                transaction.executeWithoutResult(status -> {
                    if (!orders.createVoucherOrderV2(message)) {
                        throw new IllegalStateException("创建订单未成功，等待重试");
                    }
                });
                return OrderConsumeResult.CREATED;
            } catch (OrderRejectedException rejected) {
                // 此时数据库事务已回滚；临时故障不进入这个分支。
                return cancelLocked(message, rejected.getMessage());
            }
        });
    }

    public OrderConsumeResult cancel(MessageExtend<SeckillVoucherMessage> message, String reason) {
        return withLock(message, () -> existingOrder(message) != null
                ? OrderConsumeResult.ALREADY_PROCESSED : cancelLocked(message, reason));
    }

    private OrderConsumeResult withLock(MessageExtend<SeckillVoucherMessage> message,
            Supplier<OrderConsumeResult> action) {
        validate(message);
        SeckillVoucherMessage body = message.getMessageBody();
        String lockName = RedisKeyBuild.createRedisKey(RedisKeyManage.SECKILL_ORDER_PROCESS_LOCK,
                body.getVoucherId(), body.getUserId()).getRelKey();
        RLock lock = redisson.getLock(lockName);
        // 无固定 leaseTime，使用 Redisson watchdog；竞争只触发重试，不补偿。
        if (!lock.tryLock()) {
            throw new IllegalStateException("订单正在处理中，请重试");
        }
        try {
            return action.get();
        } finally {
            lock.unlock();
        }
    }

    private void validate(MessageExtend<SeckillVoucherMessage> message) {
        SeckillVoucherMessage body = message == null ? null : message.getMessageBody();
        if (body == null || body.getOrderId() == null || body.getUserId() == null
                || body.getVoucherId() == null || body.getTraceId() == null
                || body.getBeforeQty() == null || body.getAfterQty() == null
                || body.getChangeQty() == null || message.getProducerTime() == null) {
            throw new IllegalArgumentException("下单消息缺少必要字段，禁止自动补偿");
        }
    }

    private VoucherOrder existingOrder(MessageExtend<SeckillVoucherMessage> message) {
        SeckillVoucherMessage body = message.getMessageBody();
        VoucherOrder order = orderMapper.selectOne(Wrappers.<VoucherOrder>lambdaQuery()
                .eq(VoucherOrder::getId, body.getOrderId())
                .eq(VoucherOrder::getUserId, body.getUserId())
                .eq(VoucherOrder::getVoucherId, body.getVoucherId()));
        // NORMAL 和 CANCEL 都是历史已处理订单，旧消息不得复活取消订单。
        return order;
    }

    private VoucherOrderCancellation findCancellation(SeckillVoucherMessage body) {
        return cancellations.selectOne(Wrappers.<VoucherOrderCancellation>lambdaQuery()
                .eq(VoucherOrderCancellation::getOrderId, body.getOrderId())
                .eq(VoucherOrderCancellation::getUserId, body.getUserId())
                .eq(VoucherOrderCancellation::getVoucherId, body.getVoucherId()));
    }

    private OrderConsumeResult cancelLocked(MessageExtend<SeckillVoucherMessage> message, String reason) {
        VoucherOrderCancellation cancellation = findCancellation(message.getMessageBody());
        if (cancellation == null) {
            SeckillVoucherMessage body = message.getMessageBody();
            cancellation = new VoucherOrderCancellation();
            cancellation.setOrderId(body.getOrderId());
            cancellation.setUserId(body.getUserId());
            cancellation.setVoucherId(body.getVoucherId());
            cancellation.setTraceId(ids.nextId());
            cancellation.setState("PENDING");
            cancellation.setReason(reason);
            cancellation.setMessageJson(JSON.toJSONString(message));
            cancellation.setUpdateTime(LocalDateTime.now());
            VoucherOrderCancellation pending = cancellation;
            transaction.executeWithoutResult(status -> {
                if (cancellations.insert(pending) != 1) {
                    throw new IllegalStateException("保存待补偿记录失败");
                }
            });
        }
        return completeCancellation(message, cancellation);
    }

    private OrderConsumeResult completeCancellation(MessageExtend<SeckillVoucherMessage> message,
            VoucherOrderCancellation cancellation) {
        if ("CANCELLED".equals(cancellation.getState())) {
            return OrderConsumeResult.CANCELLED;
        }
        // 恢复时使用第一次持久化的消息，不能被后续重投的字段覆盖。
        MessageExtend<SeckillVoucherMessage> original = JSON.parseObject(cancellation.getMessageJson(),
                new TypeReference<MessageExtend<SeckillVoucherMessage>>() { });
        SeckillVoucherMessage body = original.getMessageBody();
        VoucherOrder otherOrder = orderMapper.selectOne(Wrappers.<VoucherOrder>lambdaQuery()
                .eq(VoucherOrder::getUserId, body.getUserId())
                .eq(VoucherOrder::getVoucherId, body.getVoucherId())
                .eq(VoucherOrder::getStatus, OrderStatus.NORMAL.getCode()));
        // 另一张正常订单存在时必须保留购买资格。
        SeckillVoucherOrderOperate operate = otherOrder == null
                ? SeckillVoucherOrderOperate.YES : SeckillVoucherOrderOperate.NO;
        boolean compensated = redisVoucherData.rollbackRedisVoucherData(operate, cancellation.getTraceId(),
                body.getVoucherId(), body.getUserId(), body.getOrderId(),
                body.getAfterQty(), body.getChangeQty(), body.getBeforeQty());
        if (!compensated) {
            throw new IllegalStateException("Redis 补偿未完成，保留 PENDING 并重试");
        }
        transaction.executeWithoutResult(status -> {
            // 固定日志主键，兼容分片提交中途失败后重试，避免生成多个恢复日志。
            if (reconcileLogs.selectOne(Wrappers.<VoucherReconcileLog>lambdaQuery()
                    .eq(VoucherReconcileLog::getId, cancellation.getTraceId())
                    .eq(VoucherReconcileLog::getOrderId, body.getOrderId())) == null) {
                VoucherReconcileLog log = new VoucherReconcileLog();
                log.setId(cancellation.getTraceId());
                log.setTraceId(cancellation.getTraceId());
                log.setOrderId(body.getOrderId());
                log.setUserId(body.getUserId());
                log.setVoucherId(body.getVoucherId());
                log.setMessageId(original.getUuid());
                log.setLogType(LogType.RESTORE.getCode());
                log.setBusinessType("TIMEOUT".equals(cancellation.getReason())
                        ? BusinessType.TIMEOUT.getCode() : BusinessType.FAIL.getCode());
                log.setDetail(cancellation.getReason());
                log.setBeforeQty(body.getAfterQty());
                log.setChangeQty(body.getChangeQty());
                log.setAfterQty(body.getBeforeQty());
                log.setCreateTime(LocalDateTime.now());
                log.setUpdateTime(LocalDateTime.now());
                if (reconcileLogs.insert(log) != 1) {
                    throw new IllegalStateException("保存补偿日志失败");
                }
            }
            cancellation.setState("CANCELLED");
            cancellation.setUpdateTime(LocalDateTime.now());
            if (cancellations.update(cancellation, Wrappers.<VoucherOrderCancellation>lambdaUpdate()
                    .eq(VoucherOrderCancellation::getOrderId, body.getOrderId())
                    .eq(VoucherOrderCancellation::getUserId, body.getUserId())
                    .eq(VoucherOrderCancellation::getVoucherId, body.getVoucherId())) != 1) {
                throw new IllegalStateException("更新补偿终态失败");
            }
        });
        return OrderConsumeResult.CANCELLED;
    }

    @Scheduled(fixedDelayString = "${seckill.order.compensation.recoveryDelayMillis:30000}")
    public void recoverPendingCancellations() {
        for (VoucherOrderCancellation pending : cancellations.selectList(
                Wrappers.<VoucherOrderCancellation>lambdaQuery()
                        .eq(VoucherOrderCancellation::getState, "PENDING")
                        .orderByAsc(VoucherOrderCancellation::getUpdateTime).last("LIMIT 100"))) {
            try {
                MessageExtend<SeckillVoucherMessage> message = JSON.parseObject(pending.getMessageJson(),
                        new TypeReference<MessageExtend<SeckillVoucherMessage>>() { });
                cancel(message, pending.getReason());
            } catch (Exception failure) {
                log.warn("待补偿订单恢复失败，orderId={}", pending.getOrderId(), failure);
            }
        }
    }
}
