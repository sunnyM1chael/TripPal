package org.javaup.kafka.consumer;

import com.alibaba.fastjson.JSON;
import org.javaup.kafka.message.SeckillVoucherMessage;
import org.javaup.message.MessageExtend;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class SeckillVoucherConsumerTest {
    private final SeckillOrderProcessor processor = mock(SeckillOrderProcessor.class);
    private final SeckillVoucherConsumer consumer = new SeckillVoucherConsumer();
    private final Acknowledgment acknowledgment = mock(Acknowledgment.class);

    private void consume() {
        ReflectionTestUtils.setField(consumer, "orderProcessor", processor);
        String value = JSON.toJSONString(MessageExtend.of(
                new SeckillVoucherMessage(1L, 2L, 123L, 456L, 10, 1, 9, false)));
        consumer.onMessage(value, Map.of(), null, acknowledgment);
    }

    @Test
    void duplicateIsAcknowledgedNormally() {
        when(processor.process(any())).thenReturn(OrderConsumeResult.ALREADY_PROCESSED);
        consume();
        verify(acknowledgment).acknowledge();
    }

    @Test
    void completedCancellationIsAcknowledgedNormally() {
        when(processor.process(any())).thenReturn(OrderConsumeResult.CANCELLED);
        consume();
        verify(acknowledgment).acknowledge();
    }

    @Test
    void temporaryFailureIsNotAcknowledgedOrCompensatedByConsumer() {
        when(processor.process(any())).thenThrow(new IllegalStateException("DB unavailable"));
        assertThrows(IllegalStateException.class, this::consume);
        verifyNoInteractions(acknowledgment);
        verify(processor, never()).cancel(any(), any());
    }
}
