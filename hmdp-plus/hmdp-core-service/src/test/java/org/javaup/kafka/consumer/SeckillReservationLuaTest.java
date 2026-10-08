package org.javaup.kafka.consumer;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;

import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/** Uses an isolated test Redis, never flushes or touches application keys. */
@EnabledIfEnvironmentVariable(named = "SECKILL_TEST_REDIS_PORT", matches = "[0-9]+")
class SeckillReservationLuaTest {
    private LettuceConnectionFactory connection;
    private StringRedisTemplate redis;
    private List<String> keys;
    private DefaultRedisScript<Long> rollback;

    @BeforeEach
    void setUp() {
        connection = new LettuceConnectionFactory("127.0.0.1",
                Integer.parseInt(System.getenv("SECKILL_TEST_REDIS_PORT")));
        connection.afterPropertiesSet();
        redis = new StringRedisTemplate(connection);
        String tag = "{test-" + UUID.randomUUID() + "}";
        keys = List.of(tag + ":stock", tag + ":users", tag + ":traces", tag + ":owners", tag + ":compensated");
        rollback = new DefaultRedisScript<>();
        rollback.setLocation(new ClassPathResource("lua/seckillVoucherRollBack.lua"));
        rollback.setResultType(Long.class);
        redis.opsForValue().set(keys.get(0), "9");
        redis.opsForSet().add(keys.get(1), "1");
        redis.opsForHash().put(keys.get(3), "1", "123");
    }

    @AfterEach
    void tearDown() {
        if (redis != null) {
            redis.delete(keys);
        }
        if (connection != null) {
            connection.destroy();
        }
    }

    private Long compensate(String operate, String traceId) {
        return redis.execute(rollback, keys, "2", "1", "123", operate, traceId, "2", "9", "1", "10");
    }

    @Test
    void matchingReservationIsReleasedOnce() {
        assertEquals(0L, compensate("1", "999"));
        assertFalse(Boolean.TRUE.equals(redis.opsForSet().isMember(keys.get(1), "1")));
        assertNull(redis.opsForHash().get(keys.get(3), "1"));
        assertFalse(Boolean.TRUE.equals(redis.hasKey(keys.get(0))));
        assertEquals(0L, compensate("1", "1000"));
        assertEquals(1L, redis.opsForHash().size(keys.get(2)));
        assertEquals("999", redis.opsForHash().get(keys.get(4), "123"));
    }

    @Test
    void oldCompensationCannotReleaseNewOrderReservation() {
        redis.opsForHash().put(keys.get(3), "1", "124");
        assertEquals(0L, compensate("1", "999"));
        assertTrue(Boolean.TRUE.equals(redis.opsForSet().isMember(keys.get(1), "1")));
        assertEquals("124", redis.opsForHash().get(keys.get(3), "1"));
    }

    @Test
    void missingStockKeyDoesNotPreventReservationCleanup() {
        redis.delete(keys.get(0));
        assertEquals(0L, compensate("1", "999"));
        assertFalse(Boolean.TRUE.equals(redis.opsForSet().isMember(keys.get(1), "1")));
    }

    @Test
    void anotherNormalOrderKeepsPurchaseFlag() {
        assertEquals(0L, compensate("0", "999"));
        assertTrue(Boolean.TRUE.equals(redis.opsForSet().isMember(keys.get(1), "1")));
    }

    @Test
    void legacyReservationWithoutOwnerIsNotBlindlyDeleted() {
        redis.delete(keys.get(3));
        assertEquals(-2L, compensate("1", "999"));
        assertTrue(Boolean.TRUE.equals(redis.opsForSet().isMember(keys.get(1), "1")));
        assertFalse(redis.opsForHash().hasKey(keys.get(4), "123"));
    }

    @Test
    void reservationScriptRecordsOrderOwnership() {
        redis.opsForSet().remove(keys.get(1), "1");
        redis.delete(keys.get(3));
        DefaultRedisScript<String> reserve = new DefaultRedisScript<>();
        reserve.setLocation(new ClassPathResource("lua/seckillVoucher.lua"));
        reserve.setResultType(String.class);
        long now = System.currentTimeMillis();
        String result = redis.execute(reserve, keys.subList(0, 4), "2", "1",
                String.valueOf(now - 10000), String.valueOf(now + 60000), "1", "123", "456", "1", "3600");
        assertTrue(result.contains("\"code\": 0"));
        assertEquals("123", redis.opsForHash().get(keys.get(3), "1"));
        assertEquals("8", redis.opsForValue().get(keys.get(0)));
    }
}
