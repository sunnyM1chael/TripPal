package org.javaup.service.impl;

import cn.hutool.core.collection.CollectionUtil;
import cn.hutool.core.date.LocalDateTimeUtil;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.javaup.core.RedisKeyManage;
import org.javaup.entity.SeckillVoucher;
import org.javaup.entity.VoucherOrder;
import org.javaup.entity.VoucherReconcileLog;
import org.javaup.enums.LogType;
import org.javaup.enums.ReconciliationStatus;
import org.javaup.model.RedisTraceLogModel;
import org.javaup.kafka.consumer.SeckillOrderProcessor;
import org.javaup.kafka.consumer.OrderConsumeResult;
import org.javaup.kafka.message.SeckillVoucherMessage;
import org.javaup.message.MessageExtend;
import java.util.Date;
import org.javaup.redis.RedisCache;
import org.javaup.redis.RedisKeyBuild;
import org.javaup.service.IReconciliationTaskService;
import org.javaup.service.ISeckillVoucherService;
import org.javaup.service.IVoucherOrderService;
import org.javaup.service.IVoucherReconcileLogService;
import org.javaup.servicelock.LockType;
import org.javaup.servicelock.annotion.ServiceLock;
import org.springframework.aop.framework.AopContext;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import static org.javaup.constant.DistributedLockConstants.UPDATE_SECKILL_VOUCHER_STOCK_LOCK;
import static org.javaup.kafka.consumer.SeckillVoucherConsumer.MESSAGE_DELAY_TIME;

/**
 * @program: 黑马点评-plus升级版实战项目。添加 阿星不是程序员 微信，添加时备注 点评 来获取项目的完整资料
 * @description: 对账执行 接口
 * @author: 阿星不是程序员
 **/
@Service
@Slf4j
public class ReconciliationTaskServiceImpl implements IReconciliationTaskService {
    
    @Resource
    private ISeckillVoucherService seckillVoucherService;
    
    @Resource
    private IVoucherOrderService voucherOrderService;
    
    @Resource
    private IVoucherReconcileLogService voucherReconcileLogService;
    
    @Resource
    private RedisCache redisCache;
    
    @Resource
    private SeckillOrderProcessor orderProcessor;

    /** 补上 Redis 扣减后、发送前崩溃，以及发送失败回调未能持久化取消的窗口。 */
    @Scheduled(fixedDelayString = "${seckill.order.orphanRecoveryDelayMillis:60000}")
    public void recoverOrphanReservations() {
        for (SeckillVoucher voucher : seckillVoucherService.lambdaQuery().list()) {
            try {
                redisDeductTraceWithoutDbOrder(voucher.getVoucherId(), loadRedisTraceLogMap(voucher.getVoucherId()));
            } catch (Exception failure) {
                log.warn("Redis 占券流水恢复失败，voucherId={}", voucher.getVoucherId(), failure);
            }
        }
    }

    @Override
    public void reconciliationTaskExecute() {
        List<SeckillVoucher> seckillVoucherList = seckillVoucherService.lambdaQuery().list();
        for (SeckillVoucher seckillVoucher : seckillVoucherList) {
            reconciliationTaskExecute(seckillVoucher.getVoucherId());
        }
    }
    
    public void reconciliationTaskExecute(Long voucherId){
        Map<String, RedisTraceLogModel> redisTraceLogMap = loadRedisTraceLogMap(voucherId);
        redisDeductTraceWithoutDbOrder(voucherId, redisTraceLogMap);
        
        List<VoucherOrder> voucherOrderList = loadPendingOrders(voucherId);
        RedisKeyBuild traceLogKey = RedisKeyBuild.createRedisKey(RedisKeyManage.SECKILL_TRACE_LOG_TAG_KEY, voucherId);
        long ttlSeconds = resolveTraceTtlSeconds(traceLogKey, voucherId);
        for (VoucherOrder voucherOrder : voucherOrderList) {
            List<VoucherReconcileLog> logs = loadReconcileLogs(voucherOrder.getId());
            if (CollectionUtil.isEmpty(logs)) {
                ((ReconciliationTaskServiceImpl) AopContext.currentProxy())
                        .markOrderStatus(voucherOrder.getId(), ReconciliationStatus.ABNORMAL);
                continue;
            }
            boolean anyMissing = backfillMissingTraceLogs(logs, redisTraceLogMap, traceLogKey, ttlSeconds);
            
            int dbLogCount = logs.size();
            boolean markConsistent = true;
            if (dbLogCount == 1 || dbLogCount == 2) {
                if (anyMissing) {
                    ((IReconciliationTaskService) AopContext.currentProxy()).delRedisStock(voucherId);
                }
            } else {
                ((ReconciliationTaskServiceImpl) AopContext.currentProxy())
                        .markOrderStatus(voucherOrder.getId(), ReconciliationStatus.ABNORMAL);
                markConsistent = false;
            }
            if (markConsistent) {
                ((ReconciliationTaskServiceImpl) AopContext.currentProxy())
                        .markOrderStatus(voucherOrder.getId(), ReconciliationStatus.CONSISTENT);
            }
        }
    }
    
    @Override
    @ServiceLock(lockType= LockType.Write,name = UPDATE_SECKILL_VOUCHER_STOCK_LOCK,keys = {"#voucherId"})
    public void delRedisStock(Long voucherId){
        RedisKeyBuild stockKey = RedisKeyBuild.createRedisKey(RedisKeyManage.SECKILL_STOCK_TAG_KEY, voucherId);
        redisCache.del(stockKey);
    }

    private List<VoucherOrder> loadPendingOrders(Long voucherId) {
        return voucherOrderService.lambdaQuery()
                .eq(VoucherOrder::getVoucherId, voucherId)
                .le(VoucherOrder::getCreateTime, LocalDateTimeUtil.offset(LocalDateTimeUtil.now(), 2, ChronoUnit.MINUTES))
                .eq(VoucherOrder::getReconciliationStatus, ReconciliationStatus.PENDING.getCode())
                .orderByAsc(VoucherOrder::getCreateTime)
                .list();
    }

    private List<VoucherReconcileLog> loadReconcileLogs(Long orderId) {
        return voucherReconcileLogService.lambdaQuery()
                .eq(VoucherReconcileLog::getOrderId, orderId)
                .orderByAsc(VoucherReconcileLog::getCreateTime)
                .list();
    }

    private Map<String, RedisTraceLogModel> loadRedisTraceLogMap(Long voucherId) {
        return redisCache.getAllMapForHash(
                RedisKeyBuild.createRedisKey(RedisKeyManage.SECKILL_TRACE_LOG_TAG_KEY, voucherId),
                RedisTraceLogModel.class
        );
    }

    private long resolveTraceTtlSeconds(RedisKeyBuild traceLogKey, Long voucherId) {
        Long ttlSeconds = redisCache.getExpire(traceLogKey, TimeUnit.SECONDS);
        if (ttlSeconds != null && ttlSeconds > 0) {
            return ttlSeconds;
        }
        SeckillVoucher voucher = seckillVoucherService.lambdaQuery()
                .eq(SeckillVoucher::getVoucherId, voucherId)
                .one();
        long computedTtl = 3600L;
        if (voucher != null && voucher.getEndTime() != null) {
            LocalDateTime now = LocalDateTimeUtil.now();
            long secondsUntilEnd = Math.max(0L, Duration.between(now, voucher.getEndTime()).getSeconds());
            computedTtl = Math.max(1L, secondsUntilEnd + Duration.ofDays(1).getSeconds());
        }
        return computedTtl;
    }
    

    private void redisDeductTraceWithoutDbOrder(Long voucherId, Map<String, RedisTraceLogModel> traces) {
        if (voucherId == null || CollectionUtil.isEmpty(traces)) {
            return;
        }
        long now = System.currentTimeMillis();
        for (RedisTraceLogModel trace : traces.values()) {
            if (trace == null || !String.valueOf(LogType.DEDUCT.getCode()).equals(trace.getLogType())
                    || trace.getTs() == null || now - trace.getTs() < MESSAGE_DELAY_TIME + 2000) {
                continue;
            }
            try {
                // 对账也必须经过订单检查和同一业务锁，不能直接删除购买资格。
                SeckillVoucherMessage body = new SeckillVoucherMessage(Long.valueOf(trace.getUserId()),
                        voucherId, Long.valueOf(trace.getOrderId()), Long.valueOf(trace.getTraceId()),
                        trace.getBeforeQty(), trace.getChangeQty(), trace.getAfterQty(), Boolean.FALSE);
                MessageExtend<SeckillVoucherMessage> message = MessageExtend.of(body);
                message.setProducerTime(new Date(trace.getTs()));
                OrderConsumeResult result = orderProcessor.cancel(message, "RECONCILIATION_ORPHAN_RESERVATION");
                if (result == OrderConsumeResult.CANCELLED) {
                    // 终态已持久化，清理待恢复的扣减流水；恢复流水和订单补偿记录仍保留。
                    redisCache.delForHash(RedisKeyBuild.createRedisKey(
                            RedisKeyManage.SECKILL_TRACE_LOG_TAG_KEY, voucherId), trace.getTraceId());
                }
            } catch (Exception failure) {
                log.warn("对账补偿暂未完成，voucherId={}, orderId={}", voucherId, trace.getOrderId(), failure);
            }
        }
    }

    private boolean backfillMissingTraceLogs(List<VoucherReconcileLog> logs,
                                             Map<String, RedisTraceLogModel> redisTraceLogMap,
                                             RedisKeyBuild traceLogKey,
                                             long ttlSeconds) {
        boolean anyMissing = false;
        for (VoucherReconcileLog log : logs) {
            String traceIdStr = String.valueOf(log.getTraceId());
            RedisTraceLogModel existed = redisTraceLogMap.get(traceIdStr);
            if (existed != null) {
                continue;
            }
            anyMissing = true;
            RedisTraceLogModel model = new RedisTraceLogModel();
            model.setLogType(String.valueOf(log.getLogType()));
            model.setTs(LocalDateTimeUtil.toEpochMilli(log.getCreateTime()));
            model.setOrderId(String.valueOf(log.getOrderId()));
            model.setTraceId(traceIdStr);
            model.setUserId(String.valueOf(log.getUserId()));
            model.setVoucherId(String.valueOf(log.getVoucherId()));
            model.setBeforeQty(log.getBeforeQty());
            model.setChangeQty(log.getChangeQty());
            model.setAfterQty(log.getAfterQty());
            redisCache.putHash(traceLogKey, traceIdStr, model);
            Long currentTtl = redisCache.getExpire(traceLogKey, TimeUnit.SECONDS);
            if (currentTtl == null || currentTtl <= 0) {
                redisCache.expire(traceLogKey, ttlSeconds, TimeUnit.SECONDS);
            }
        }
        return anyMissing;
    }

    @Transactional(rollbackFor = Exception.class)
    public void markOrderStatus(Long orderId, ReconciliationStatus status) {
        voucherOrderService.lambdaUpdate()
                .set(VoucherOrder::getReconciliationStatus, status.getCode())
                .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                .eq(VoucherOrder::getId, orderId)
                .update();
        voucherReconcileLogService.lambdaUpdate()
                .set(VoucherReconcileLog::getReconciliationStatus, status.getCode())
                .set(VoucherReconcileLog::getUpdateTime, LocalDateTime.now())
                .eq(VoucherReconcileLog::getOrderId, orderId)
                .update();
    }
}
