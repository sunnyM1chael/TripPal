package org.javaup.kafka.consumer;

/** 消费结果；重复消息不是下单失败。 */
public enum OrderConsumeResult {
    CREATED, ALREADY_PROCESSED, CANCELLED
}
