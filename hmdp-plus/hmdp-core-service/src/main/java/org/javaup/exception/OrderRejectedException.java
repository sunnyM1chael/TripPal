package org.javaup.exception;

/** 已确认的业务拒绝；仅此类错误允许立即进入取消补偿。 */
public class OrderRejectedException extends RuntimeException {
    public OrderRejectedException(String message) {
        super(message);
    }
}
