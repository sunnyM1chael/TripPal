package org.javaup.config;

import org.javaup.consumer.AbstractConsumerHandler;
import org.javaup.kafka.consumer.SeckillOrderProcessor;
import org.javaup.kafka.message.SeckillVoucherMessage;
import org.javaup.message.MessageExtend;
import org.springframework.boot.autoconfigure.kafka.ConcurrentKafkaListenerContainerFactoryConfigurer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.util.backoff.FixedBackOff;

import java.util.Map;

@Configuration
@EnableScheduling
public class SeckillOrderKafkaConfig {
    @Bean
    public ConcurrentKafkaListenerContainerFactory<Object, Object> seckillOrderKafkaListenerContainerFactory(
            ConcurrentKafkaListenerContainerFactoryConfigurer configurer,
            ConsumerFactory<Object, Object> consumerFactory, SeckillOrderProcessor processor) {
        ConcurrentKafkaListenerContainerFactory<Object, Object> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        configurer.configure(factory, consumerFactory);
        factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL_IMMEDIATE);
        AbstractConsumerHandler<SeckillVoucherMessage> decoder =
                new AbstractConsumerHandler<>(SeckillVoucherMessage.class) {
                    @Override
                    protected void doConsume(MessageExtend<SeckillVoucherMessage> message) { }
                };
        DefaultErrorHandler handler = new DefaultErrorHandler((record, failure) -> {
            MessageExtend<SeckillVoucherMessage> message = decoder.convert((String) record.value(), Map.of());
            // 耗尽重试后也要核对终态。补偿失败或锁冲突继续抛异常，禁止跳过消息。
            processor.cancel(message, "CONSUME_RETRIES_EXHAUSTED");
        }, new FixedBackOff(1000L, 3L));
        handler.setAckAfterHandle(false);
        handler.setCommitRecovered(true);
        factory.setCommonErrorHandler(handler);
        return factory;
    }
}
