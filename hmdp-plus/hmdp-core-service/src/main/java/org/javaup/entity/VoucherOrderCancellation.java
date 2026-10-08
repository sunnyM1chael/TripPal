package org.javaup.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

/** 先持久化取消决定，再补偿 Redis；进程重启后继续待补偿任务。 */
@Data
@TableName("tb_voucher_order_cancellation")
public class VoucherOrderCancellation {
    @TableId
    private Long orderId;
    private Long userId;
    private Long voucherId;
    private Long traceId;
    private String state;
    private String reason;
    private String messageJson;
    private LocalDateTime updateTime;
}
