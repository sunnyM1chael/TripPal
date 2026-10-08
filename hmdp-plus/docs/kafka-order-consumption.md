# 秒杀消息消费与补偿修改说明

## 业务规则

同一订单的重复消息表示“以前已经处理过”，不是“下单失败”。

- 本次创建成功：返回 CREATED，执行成功后通知、订阅清理和统计，手动确认消息。
- 同一订单已经存在：返回 ALREADY_PROCESSED，只确认消息，不补偿、不重复统计。
- 已有取消终态：返回 CANCELLED，只确认消息，不重新创建。
- 锁竞争、数据库或 Redis 暂时不可用：抛异常重试，不立即回滚占券。
- 尚未处理且超过 10 秒、确定的业务拒绝、发送失败或重试耗尽：先检查数据库订单，再决定取消。

原注解 `@RepeatExecuteLimit` 默认不保存成功标记，且把锁竞争和重复成功统一抛异常。
下单入口已移除该注解，改由专门的业务处理器协调；其他业务使用该公共注解的行为保持原样。

## 核心业务代码

消费者的分支现在是：

```java
OrderConsumeResult result = orderProcessor.process(message);
if (result == OrderConsumeResult.CREATED) {
    afterOrderCreated(message);
}
// onMessage 在上述处理正常返回后 acknowledge；异常时不会执行这一步。
```

`SeckillOrderProcessor.process()` 的顺序：

1. 校验消息必填字段。
2. 获取“同一张券、同一用户”的 Redisson 锁，竞争失败抛异常等待重试。
3. 按订单 ID + 用户 ID + 券 ID 查询数据库，正常或已取消的历史订单均返回 ALREADY_PROCESSED。
4. 查询持久化取消记录，CANCELLED 直接返回，PENDING 继续原补偿。
5. 检查消息是否超时。超时取消必须在查重之后。
6. 使用事务创建订单，数据库事务完成后才释放业务锁。
7. 仅确定的业务拒绝进入补偿，临时异常原样向外传播。

取消流程：

1. 持有同一业务锁，再次核对是否已有订单。
2. 创建 PENDING 记录并提交，保存原消息、原因和固定补偿流水 ID。
3. 执行 Redis 补偿。失败继续保持 PENDING，不确认消息。
4. 写固定主键的恢复日志并将记录改为 CANCELLED。
5. 后续重投只读取终态；数据库写入失败后重试使用原流水，不重复生成恢复日志。

`SeckillVoucherProducer` 的失败回调也使用此取消流程。
发送确认超时不代表消息一定没有送达；如果订单已经落库，回调只识别为已处理。

## Redis 变化

原用户购买 SET 保留，增加两个 HASH（均使用券 ID 作为 hash tag）：

- `seckill:reservation:owner:{voucherId}`：用户 ID → 当前占券订单 ID。
- `seckill:compensated:order:{voucherId}`：已补偿订单 ID → 补偿流水 ID。

预扣脚本同时写 owner。普通抢券和自动发券都已补齐这个脚本参数。

回滚脚本先检查已补偿标记。同一订单重复补偿直接返回成功，不重新写恢复流水。
只有 owner 等于本次订单 ID，才允许删除用户购买标记；另一张正常订单存在时保留购买标记。
库存缓存不存在也可以完成资格清理。库存操作仍是删除缓存后重新加载，不是直接加一。

若存在历史购买标记但没有 owner，脚本返回 -2，保留 PENDING 并记录回滚失败日志。
必须人工核对归属，确认后补齐 owner，让恢复任务继续；不能猜测归属并删除用户资格。

补偿标记和取消终态不自动过期。清理前必须考虑 Kafka 保留期、人工回放期和订单生命周期，
避免旧消息在去重数据被清理后重新生效。

## Kafka 错误处理与恢复

仅订单监听器使用专门的容器工厂，不影响缓存广播消费者。
消费失败后间隔 1 秒重试 3 次；恢复器随后通过处理器核对订单并尝试取消。
恢复器成功返回才提交恢复消息的 offset；锁竞争、数据库查询失败、无效消息或补偿失败时
恢复器继续抛异常，消息不能被静默跳过。

有两个自动恢复入口：

- 每 30 秒读取最多 100 条 PENDING 取消记录并恢复，支持进程重启后的续做。
- 每 60 秒扫描 Redis 扣减流水，超过 12 秒仍需核对的占券记录经过同一处理器决定取消。
  这覆盖 Redis 预扣后发送前崩溃、失败回调未保存取消记录的窗口。

可配置 `seckill.order.compensation.recoveryDelayMillis` 和 `seckill.order.orphanRecoveryDelayMillis`。
扫描按当前项目数据规模设计，券和流水数量较大时需要分批扫描及专门调度。

## 部署步骤

1. 暂停普通抢券、自动发券和取消订单入口，并停止旧版本消费者，避免新旧 Lua 混用。
2. 备份数据库；在实际配置的数据库执行 `sql/migrations/20261008_order_cancellation.sql`。
   脚本为 hmdp_0 和 hmdp_1 创建两张物理表，不删除现有数据。
   当前仓库配置 ds_0、ds_1 都指向 hmdp_1，部署时应核对真实数据源和库名。
3. 核对历史购买 SET，按实际订单/占券流水回填 owner。仅能确定归属的记录才回填，
   无法确定的保留并人工核查，禁止清空购买 SET。
4. 部署全部新版本实例，再恢复消费者和业务入口。
5. 观察 PENDING 数量、回滚失败日志和 Kafka lag；确认未出现无法核对归属的历史记录。

此次交付不自动连接或迁移业务数据库，也不部署运行中的应用。

## 验证方式与边界

需要 Java 17。针对性测试使用 JUnit 5 + Mockito；Lua 测试使用真实的独立 Redis。

```powershell
$env:SECKILL_TEST_REDIS_PORT='16389'
mvn -pl hmdp-core-service -am test '-Dtest=SeckillOrderProcessorTest,SeckillReservationLuaTest,SeckillVoucherConsumerTest' '-Dsurefire.failIfNoSpecifiedTests=false' '-DfailIfNoTests=false'
```

Lua 测试只创建随机测试前缀的键并清理这些键，不执行 FLUSHDB。
不设置 Redis 测试端口时 Lua 集成测试会跳过。

覆盖重复/迟到/已取消消息、锁竞争、事务提交顺序、临时数据库故障、业务拒绝、
待补偿恢复、固定日志去重、消费者 ACK，以及真实 Lua 的订单归属和补偿去重。

数据库和 Kafka 的完整端到端故障演练仍需在部署环境完成。
现有项目的跨数据库分片事务配置未在此次变更中升级为 XA，不能把本次修复当成跨库原子性保证。
Redis 流水恢复还依赖 Redis 数据持久性和流水保留期。
通知和排行榜仍属于数据库提交后的异步附属操作，未增加事务消息机制，崩溃时可能遗漏；
本次只保证重复消息不会重新触发这些操作，不宣称它们严格执行一次。
