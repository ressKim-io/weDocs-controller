---
name: distributed-lock
description: "Distributed Lock Patterns — MSA/다중 서버 환경에서의 분산 락 패턴 Use when working with msa 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Distributed Lock Patterns

MSA/다중 서버 환경에서의 분산 락 패턴

## Quick Reference (결정 트리)

```
분산 락 필요?
    │
    ├─ 스케줄러 중복 방지 ──────> ShedLock
    │
    ├─ 단순 크리티컬 섹션 ──────> Redis + Redisson
    │
    ├─ 높은 가용성 필요 ────────> Redlock (다중 Redis 노드)
    │
    └─ 강력한 일관성 필요 ──────> ZooKeeper / etcd
```

| 상황 | 분산 락 필요 |
|------|-------------|
| 단일 서버 | ❌ (로컬 Mutex/Lock) |
| 다중 서버 + DB만 | △ (DB 락 가능) |
| MSA + 서비스 간 조율 | ✅ |
| 스케줄러 중복 방지 | ✅ |

---

## CRITICAL: Spring Boot + Redisson

**IMPORTANT**: try-finally로 반드시 락 해제

```groovy
implementation 'org.redisson:redisson-spring-boot-starter:3.27.0'
```

```java
@Service
@RequiredArgsConstructor
public class StockService {
    private final RedissonClient redissonClient;

    public void decreaseStock(Long productId, int quantity) {
        String lockKey = "lock:product:" + productId;
        RLock lock = redissonClient.getLock(lockKey);

        try {
            // 최대 5초 대기, 락 획득 후 3초 유지
            boolean acquired = lock.tryLock(5, 3, TimeUnit.SECONDS);
            if (!acquired) {
                throw new LockAcquisitionException("락 획득 실패");
            }

            // 크리티컬 섹션
            Product product = productRepository.findById(productId).orElseThrow();
            product.decreaseStock(quantity);
            productRepository.save(product);

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new LockAcquisitionException("락 획득 중 인터럽트");
        } finally {
            if (lock.isLocked() && lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

### AOP로 깔끔하게

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface DistributedLock {
    String key();                    // SpEL 지원
    long waitTime() default 5000;
    long leaseTime() default 3000;
}

// 사용
@DistributedLock(key = "'lock:product:' + #productId")
@Transactional
public void decreaseStock(Long productId, int quantity) {
    Product product = productRepository.findById(productId).orElseThrow();
    product.decreaseStock(quantity);
}
```

---

## Go + Redsync (Redlock)

```go
import (
    "github.com/go-redsync/redsync/v4"
    "github.com/go-redsync/redsync/v4/redis/goredis/v9"
)

func DecreaseStock(ctx context.Context, rs *redsync.Redsync, productID int64, qty int) error {
    mutex := rs.NewMutex(
        fmt.Sprintf("lock:product:%d", productID),
        redsync.WithExpiry(3*time.Second),
        redsync.WithTries(3),
        redsync.WithRetryDelay(100*time.Millisecond),
    )

    if err := mutex.LockContext(ctx); err != nil {
        return fmt.Errorf("락 획득 실패: %w", err)
    }
    defer mutex.UnlockContext(ctx)

    return updateStock(productID, qty)
}
```

### 간단한 Redis 락 (단일 노드)

```go
func (l *Lock) Acquire(ctx context.Context) (bool, error) {
    return l.client.SetNX(ctx, l.key, l.value, l.duration).Result()
}

func (l *Lock) Release(ctx context.Context) error {
    // Lua: 본인 락만 해제
    script := `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        end
        return 0
    `
    _, err := l.client.Eval(ctx, script, []string{l.key}, l.value).Result()
    return err
}
```

---

## 스케줄러 중복 방지 (ShedLock)

```groovy
implementation 'net.javacrumbs.shedlock:shedlock-spring:5.10.0'
implementation 'net.javacrumbs.shedlock:shedlock-provider-redis-spring:5.10.0'
```

```java
@Configuration
@EnableSchedulerLock(defaultLockAtMostFor = "10m")
public class ShedLockConfig {
    @Bean
    public LockProvider lockProvider(RedisConnectionFactory factory) {
        return new RedisLockProvider(factory);
    }
}

@Scheduled(cron = "0 0 * * * *")
@SchedulerLock(
    name = "hourlyTask",
    lockAtLeastFor = "5m",   // 최소 유지 (중복 방지)
    lockAtMostFor = "10m"    // 최대 유지 (장애 시 해제)
)
public void hourlyTask() {
    // 다중 인스턴스 중 하나만 실행
}
```

---

## Fencing Token (TTL 만료 문제 해결)

GC pause 등으로 TTL 만료 후 작업 계속되는 문제 방지

```java
// Fencing Token 발급
long token = tokenCounter.incrementAndGet();

// DB 업데이트 시 토큰 검증
int updated = jdbcTemplate.update(
    "UPDATE product SET stock = stock - ?, last_token = ? " +
    "WHERE id = ? AND (last_token IS NULL OR last_token < ?)",
    quantity, token, productId, token
);

if (updated == 0) {
    throw new StaleTokenException("오래된 토큰");
}
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| TTL 없음 | 영구 락 | 항상 TTL 설정 |
| 고유 ID 없이 해제 | 타 클라이언트 락 해제 | UUID로 본인 확인 |
| finally 없음 | 락 누수 | try-finally 필수 |
| 락 범위 너무 큼 | 병목 | 최소 범위로 |
| TTL만 믿음 | GC pause 문제 | Fencing Token |
| 단일 Redis | 장애 시 중단 | Redlock/클러스터 |

---

## 체크리스트

- [ ] 락 키는 리소스별 고유 (예: `lock:product:{id}`)
- [ ] TTL 적절히 설정 (작업 시간 + 여유)
- [ ] UUID로 락 소유자 식별
- [ ] try-finally로 반드시 해제
- [ ] 트랜잭션은 락 해제 전에 커밋
- [ ] 스케줄러는 ShedLock 사용
- [ ] 크리티컬한 경우 Fencing Token 검토
