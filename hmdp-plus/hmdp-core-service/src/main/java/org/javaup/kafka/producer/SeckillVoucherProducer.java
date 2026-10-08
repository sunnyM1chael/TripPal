package org.javaup.kafka.producer;

import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.javaup.AbstractProducerHandler;
import org.javaup.kafka.message.SeckillVoucherMessage;
import org.javaup.kafka.consumer.SeckillOrderProcessor;
import org.javaup.message.MessageExtend;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

/**
 * @program: 黑马点评-plus升级版实战项目。添加 阿星不是程序员 微信，添加时备注 点评 来获取项目的完整资料
 * @description: Kafka 生产者：发送秒杀券
 * @author: 阿星不是程序员
 **/
@Slf4j
@Component
public class SeckillVoucherProducer extends AbstractProducerHandler<MessageExtend<SeckillVoucherMessage>> {



    @Resource
    private SeckillOrderProcessor orderProcessor;

    public SeckillVoucherProducer(final KafkaTemplate<String,MessageExtend<SeckillVoucherMessage>> kafkaTemplate) {
        super(kafkaTemplate);
    }

    @Override
    protected void afterSendFailure(final String topic, final MessageExtend<SeckillVoucherMessage> message, final Throwable throwable) {
        super.afterSendFailure(topic, message, throwable);
        // 发送异常可能是确认超时，订单可能已经被消费；先核对结果再决定取消。
        orderProcessor.cancel(message, "SEND_FAILURE");
    }
}
