package org.javaup.kafka.consumer;

import com.alibaba.fastjson.JSON;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import org.javaup.entity.VoucherOrder;
import org.javaup.entity.VoucherOrderCancellation;
import org.javaup.exception.OrderRejectedException;
import org.javaup.kafka.message.SeckillVoucherMessage;
import org.javaup.kafka.redis.RedisVoucherData;
import org.javaup.mapper.VoucherOrderCancellationMapper;
import org.javaup.mapper.VoucherOrderMapper;
import org.javaup.message.MessageExtend;
import org.javaup.service.IVoucherOrderService;
import org.javaup.mapper.VoucherReconcileLogMapper;
import org.javaup.entity.VoucherReconcileLog;
import org.javaup.toolkit.SnowflakeIdGenerator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.javaup.core.SpringUtil;
import org.mockito.MockedStatic;
import org.mockito.InOrder;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.util.Date;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class SeckillOrderProcessorTest {
    private IVoucherOrderService orders;
    private VoucherOrderMapper orderMapper;
    private VoucherOrderCancellationMapper cancellations;
    private RedisVoucherData redis;
    private VoucherReconcileLogMapper logs;
    private PlatformTransactionManager tx;
    private RLock lock;
    private SeckillOrderProcessor processor;
    private MessageExtend<SeckillVoucherMessage> message;
    private MockedStatic<SpringUtil> spring;

    @BeforeEach
    void setUp() {
        spring = mockStatic(SpringUtil.class);
        spring.when(SpringUtil::getPrefixDistinctionName).thenReturn("test");
        orders = mock(IVoucherOrderService.class);
        orderMapper = mock(VoucherOrderMapper.class);
        cancellations = mock(VoucherOrderCancellationMapper.class);
        redis = mock(RedisVoucherData.class);
        logs = mock(VoucherReconcileLogMapper.class);
        tx = mock(PlatformTransactionManager.class);
        when(tx.getTransaction(any(TransactionDefinition.class))).thenReturn(new SimpleTransactionStatus());
        RedissonClient redisson = mock(RedissonClient.class);
        lock = mock(RLock.class);
        when(redisson.getLock(anyString())).thenReturn(lock);
        when(lock.tryLock()).thenReturn(true);
        SnowflakeIdGenerator ids = mock(SnowflakeIdGenerator.class);
        when(ids.nextId()).thenReturn(999L);
        processor = new SeckillOrderProcessor(orders, orderMapper, cancellations, redis, logs, ids, redisson, tx);
        message = MessageExtend.of(new SeckillVoucherMessage(1L, 2L, 123L, 456L, 10, 1, 9, false));
    }

    @AfterEach
    void tearDown() {
        spring.close();
    }

    @Test
    void duplicateAfterTimeoutDoesNotCompensateOrCreate() {
        message.setProducerTime(new Date(System.currentTimeMillis() - 60000));
        when(orderMapper.selectOne(any(Wrapper.class))).thenReturn(new VoucherOrder().setId(123L));
        assertEquals(OrderConsumeResult.ALREADY_PROCESSED, processor.process(message));
        verifyNoInteractions(orders, redis, cancellations, logs);
    }

    @Test
    void cancelledExistingOrderCannotBeRecreated() {
        when(orderMapper.selectOne(any(Wrapper.class)))
                .thenReturn(new VoucherOrder().setId(123L).setStatus(2));
        assertEquals(OrderConsumeResult.ALREADY_PROCESSED, processor.process(message));
        verifyNoInteractions(orders, redis);
    }

    @Test
    void lockContentionDoesNotCompensateOrAcknowledge() {
        when(lock.tryLock()).thenReturn(false);
        assertThrows(IllegalStateException.class, () -> processor.process(message));
        verifyNoInteractions(orders, redis, cancellations, tx);
        verify(lock, never()).unlock();
    }

    @Test
    void transactionCommitsBeforeBusinessLockIsReleased() {
        when(orders.createVoucherOrderV2(message)).thenReturn(true);
        assertEquals(OrderConsumeResult.CREATED, processor.process(message));
        InOrder sequence = inOrder(orders, tx, lock);
        sequence.verify(orders).createVoucherOrderV2(message);
        sequence.verify(tx).commit(any());
        sequence.verify(lock).unlock();
        verifyNoInteractions(redis);
    }

    @Test
    void temporaryDatabaseFailureRollsBackTransactionButNotReservation() {
        when(orders.createVoucherOrderV2(message)).thenThrow(new IllegalStateException("DB unavailable"));
        assertThrows(IllegalStateException.class, () -> processor.process(message));
        verify(tx).rollback(any());
        verifyNoInteractions(redis);
        verify(cancellations, never()).insert(any(VoucherOrderCancellation.class));
    }

    @Test
    void completedCancellationDoesNotCreateOrCompensateAgain() {
        when(cancellations.selectOne(any(Wrapper.class))).thenReturn(pending("CANCELLED"));
        assertEquals(OrderConsumeResult.CANCELLED, processor.process(message));
        verifyNoInteractions(orders, redis, logs);
    }

    @Test
    void timeoutPersistsDecisionBeforeCompensation() {
        message.setProducerTime(new Date(System.currentTimeMillis() - 60000));
        when(cancellations.insert(any(VoucherOrderCancellation.class))).thenReturn(1);
        assertThrows(IllegalStateException.class, () -> processor.process(message));
        InOrder sequence = inOrder(cancellations, tx, redis);
        sequence.verify(cancellations).insert(any(VoucherOrderCancellation.class));
        sequence.verify(tx).commit(any());
        sequence.verify(redis).rollbackRedisVoucherData(any(), eq(999L), eq(2L), eq(1L), eq(123L),
                eq(9), eq(1), eq(10));
        verifyNoInteractions(orders, logs);
        verify(cancellations, never()).update(any(VoucherOrderCancellation.class), any(Wrapper.class));
    }

    @Test
    void pendingCancellationRetriesUsingOriginalTraceIdAndThenCommitsTerminalState() {
        when(cancellations.selectOne(any(Wrapper.class))).thenReturn(pending("PENDING"));
        when(redis.rollbackRedisVoucherData(any(), anyLong(), anyLong(), anyLong(), anyLong(),
                anyInt(), anyInt(), anyInt())).thenReturn(true);
        when(logs.insert(any(VoucherReconcileLog.class))).thenReturn(1);
        when(cancellations.update(any(VoucherOrderCancellation.class), any(Wrapper.class))).thenReturn(1);
        assertEquals(OrderConsumeResult.CANCELLED, processor.process(message));
        verify(redis).rollbackRedisVoucherData(any(), eq(999L), eq(2L), eq(1L), eq(123L), eq(9), eq(1), eq(10));
        verify(cancellations).update(argThat((VoucherOrderCancellation c) -> "CANCELLED".equals(c.getState())),
                any(Wrapper.class));
        verifyNoInteractions(orders);
    }

    @Test
    void ambiguousSendFailureChecksOrderBeforeCancelling() {
        when(orderMapper.selectOne(any(Wrapper.class))).thenReturn(new VoucherOrder().setId(123L));
        assertEquals(OrderConsumeResult.ALREADY_PROCESSED, processor.cancel(message, "SEND_FAILURE"));
        verifyNoInteractions(redis, cancellations);
    }

    @Test
    void businessRejectionRollsBackBeforePersistingCancellation() {
        when(orders.createVoucherOrderV2(message)).thenThrow(new OrderRejectedException("DB_STOCK_EXHAUSTED"));
        when(cancellations.insert(any(VoucherOrderCancellation.class))).thenReturn(1);
        assertThrows(IllegalStateException.class, () -> processor.process(message));
        InOrder sequence = inOrder(tx, cancellations);
        sequence.verify(tx).rollback(any());
        sequence.verify(cancellations).insert(any(VoucherOrderCancellation.class));
    }

    @Test
    void existingCompensationLogIsNotInsertedAgainAfterPartialCommit() {
        when(cancellations.selectOne(any(Wrapper.class))).thenReturn(pending("PENDING"));
        when(redis.rollbackRedisVoucherData(any(), anyLong(), anyLong(), anyLong(), anyLong(),
                anyInt(), anyInt(), anyInt())).thenReturn(true);
        when(logs.selectOne(any(Wrapper.class))).thenReturn(new VoucherReconcileLog());
        when(cancellations.update(any(VoucherOrderCancellation.class), any(Wrapper.class))).thenReturn(1);
        assertEquals(OrderConsumeResult.CANCELLED, processor.process(message));
        verify(logs, never()).insert(any(VoucherReconcileLog.class));
    }

    @Test
    void failedCompensationLogDoesNotCommitCancelledState() {
        when(cancellations.selectOne(any(Wrapper.class))).thenReturn(pending("PENDING"));
        when(redis.rollbackRedisVoucherData(any(), anyLong(), anyLong(), anyLong(), anyLong(),
                anyInt(), anyInt(), anyInt())).thenReturn(true);
        assertThrows(IllegalStateException.class, () -> processor.process(message));
        verify(cancellations, never()).update(any(VoucherOrderCancellation.class), any(Wrapper.class));
        verify(tx).rollback(any());
    }

    private VoucherOrderCancellation pending(String state) {
        VoucherOrderCancellation record = new VoucherOrderCancellation();
        record.setOrderId(123L);
        record.setUserId(1L);
        record.setVoucherId(2L);
        record.setTraceId(999L);
        record.setState(state);
        record.setReason("TIMEOUT");
        record.setMessageJson(JSON.toJSONString(message));
        return record;
    }
}
