---
name: python-performance
description: "Python Performance Optimization — 프로파일링, 메모리 최적화, 캐싱, 동시성, 직렬화 성능 튜닝 가이드. Use when working with python 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Python Performance Optimization

프로파일링, 메모리 최적화, 캐싱, 동시성, 직렬화 성능 튜닝 가이드.

## Quick Reference

```
병목 유형?
├── I/O-bound ─────────> asyncio / aiohttp / asyncpg
├── CPU-bound ─────────> multiprocessing / ProcessPoolExecutor
├── 메모리 과다 ───────> generators, __slots__, gc tuning
├── 직렬화 느림 ───────> orjson / msgpack
├── DB 쿼리 느림 ──────> 인덱스, 쿼리 최적화, connection pool
└── 반복 계산 ─────────> lru_cache / Redis cache

프로파일링 도구 선택?
├── CPU 전체 ──────────> cProfile + snakeviz
├── CPU 실시간 ────────> py-spy (flame graph)
├── 줄 단위 CPU ───────> line_profiler
├── 메모리 전체 ───────> tracemalloc
├── 줄 단위 메모리 ────> memory_profiler
├── 메모리 누수 ───────> objgraph
└── 벤치마크 ──────────> timeit / pytest-benchmark
```

---

## Profiling Tools

### cProfile (Built-in CPU Profiler)

```python
import cProfile
import pstats

# Command line
# python -m cProfile -s cumulative app.py
# python -m cProfile -o output.prof app.py

# Programmatic
def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()

    # 프로파일할 코드
    result = expensive_function()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)  # 상위 20개
    return result

# Visualize with snakeviz
# pip install snakeviz
# snakeviz output.prof  → 브라우저에서 인터랙티브 확인
```

### py-spy (Flame Graphs, No Code Changes)

```bash
# 실행 중인 프로세스에 attach (no restart needed)
py-spy top --pid <PID>

# Flame graph 생성
py-spy record --pid <PID> -o profile.svg --duration 30

# 새 프로세스 시작하면서 프로파일링
py-spy record -o profile.svg -- python app.py

# 특정 스레드만
py-spy dump --pid <PID>
```

### line_profiler (Line-by-Line)

```python
# pip install line-profiler

# @profile 데코레이터 사용
@profile
def compute_statistics(data: list[float]) -> dict:
    total = sum(data)               # 이 줄의 시간
    mean = total / len(data)        # 이 줄의 시간
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    return {"mean": mean, "variance": variance, "std": variance ** 0.5}

# 실행: kernprof -l -v script.py
```

### tracemalloc (Memory Tracking)

```python
import tracemalloc

tracemalloc.start()

# 메모리를 사용하는 코드
data = process_large_dataset()

# 스냅샷 비교
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

print("Top 10 memory allocations:")
for stat in top_stats[:10]:
    print(stat)

# 두 시점 비교 (누수 탐지)
snapshot1 = tracemalloc.take_snapshot()
# ... more processing ...
snapshot2 = tracemalloc.take_snapshot()

diff = snapshot2.compare_to(snapshot1, "lineno")
for stat in diff[:10]:
    print(stat)  # 증가량 확인
```

### memory_profiler (Line-by-Line Memory)

```python
# pip install memory-profiler

from memory_profiler import profile

@profile
def memory_heavy_function():
    a = [1] * (10 ** 6)       # 이 줄의 메모리 증가량
    b = [2] * (2 * 10 ** 7)   # 이 줄의 메모리 증가량
    del b                      # 메모리 해제
    return a

# 실행: python -m memory_profiler script.py
```

## Memory Optimization

### __slots__

```python
import sys

# 일반 클래스: __dict__ 사용 (~200 bytes/instance)
class UserNormal:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

# __slots__: 고정 속성만 (~56 bytes/instance)
class UserSlots:
    __slots__ = ("name", "age")

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

# 100만 개 객체: ~200MB vs ~56MB (약 70% 절감)
# dataclass와 조합
from dataclasses import dataclass

@dataclass(slots=True)
class Point:
    x: float
    y: float
```

### Generators vs Lists

```python
# BAD: 전체 리스트를 메모리에 로드
def get_squares_list(n: int) -> list[int]:
    return [x ** 2 for x in range(n)]  # n=10^7 → ~80MB

# GOOD: Generator (lazy evaluation)
def get_squares_gen(n: int) -> Iterator[int]:
    return (x ** 2 for x in range(n))  # ~0MB

# GOOD: itertools for memory-efficient operations
import itertools

# 첫 N개만 처리
first_100 = itertools.islice(large_generator(), 100)

# 조건까지만 처리
until_limit = itertools.takewhile(lambda x: x < 1000, generator())

# 체이닝 (리스트 연결 없이)
combined = itertools.chain(gen1(), gen2(), gen3())

# 대량 파일 처리
def process_large_file(path: str) -> Iterator[dict]:
    with open(path) as f:
        for line in f:  # 한 줄씩 읽기 (전체 로드 X)
            yield parse_line(line)
```

### weakref and gc Tuning

```python
import weakref
import gc

# weakref: 순환 참조 방지, 캐시에 유용
class Cache:
    def __init__(self) -> None:
        self._cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

    def get(self, key: str) -> object | None:
        return self._cache.get(key)

    def set(self, key: str, value: object) -> None:
        self._cache[key] = value
    # value에 대한 다른 참조가 없으면 자동 삭제됨

# GC tuning for throughput
gc.set_threshold(50000, 30, 20)  # 기본값: (700, 10, 10)
# Generation 0 threshold 높이면 GC 빈도 감소, latency 개선

# GC 비활성화 (수동 관리)
gc.disable()
# ... 대량 처리 ...
gc.collect()  # 수동 실행
gc.enable()
```

## Caching

### functools.lru_cache

```python
from functools import lru_cache, cache

# lru_cache: 최근 사용 순 캐시 (maxsize 지정)
@lru_cache(maxsize=256)
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# cache: 무제한 캐시 (Python 3.9+, lru_cache(maxsize=None) 동일)
@cache
def expensive_computation(x: int, y: int) -> float:
    return complex_math(x, y)

# 캐시 정보 확인
print(fibonacci.cache_info())
# CacheInfo(hits=97, misses=100, maxsize=256, currsize=100)

# 캐시 초기화
fibonacci.cache_clear()
```

### cachetools (고급 캐싱)

```python
from cachetools import TTLCache, LRUCache, cached
import asyncio

# TTL 기반 캐시
user_cache = TTLCache(maxsize=1000, ttl=300)  # 5분 TTL

@cached(cache=user_cache)
def get_user(user_id: int) -> dict:
    return db.query("SELECT * FROM users WHERE id = %s", user_id)

# Async compatible with lock
import threading

lock = threading.Lock()

@cached(cache=TTLCache(maxsize=500, ttl=60), lock=lock)
def get_config(key: str) -> str:
    return fetch_remote_config(key)
```

### Redis Cache Pattern

```python
import json
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

def redis_cache(ttl: int = 300, prefix: str = "cache"):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = f"{prefix}:{func.__name__}:{args}:{sorted(kwargs.items())}"
            client = RedisPool.client()

            cached = await client.get(key)
            if cached is not None:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            await client.setex(key, ttl, json.dumps(result, default=str))
            return result
        return wrapper
    return decorator

@redis_cache(ttl=600, prefix="user")
async def get_user_profile(user_id: int) -> dict:
    return await db.fetch_user(user_id)
```

## Concurrency

### multiprocessing (CPU-bound)

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def cpu_heavy_task(data: list[float]) -> float:
    return sum(x ** 2 for x in data)

def parallel_compute(datasets: list[list[float]], workers: int = 4) -> list[float]:
    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(cpu_heavy_task, data): i for i, data in enumerate(datasets)}
        for future in as_completed(futures):
            idx = futures[future]
            results.append((idx, future.result()))
    return [r for _, r in sorted(results)]
```

### ThreadPoolExecutor (Blocking I/O in Async)

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

async def async_wrapper_for_sync(sync_func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, sync_func, *args)

# Usage in FastAPI
async def endpoint():
    # 동기 라이브러리를 async에서 사용
    result = await async_wrapper_for_sync(legacy_sync_function, arg1, arg2)
    return result
```

## Serialization Performance

```python
import json
import orjson
import msgpack
import timeit

data = {"users": [{"id": i, "name": f"user_{i}"} for i in range(1000)]}

# stdlib json: baseline
json.dumps(data)  # ~1.0ms

# orjson: 3-10x faster
orjson.dumps(data)  # ~0.1ms, returns bytes
orjson.loads(orjson.dumps(data))

# msgpack: binary format, smaller size
msgpack.packb(data)  # ~0.15ms, smaller output
msgpack.unpackb(msgpack.packb(data))

# orjson options
orjson.dumps(
    data,
    option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2,
)

# FastAPI with orjson
from fastapi.responses import ORJSONResponse

app = FastAPI(default_response_class=ORJSONResponse)
```

## Database Query Optimization

```python
# 1. Use EXPLAIN ANALYZE
# EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@test.com';

# 2. Index columns used in WHERE, JOIN, ORDER BY
# CREATE INDEX idx_users_email ON users (email);
# CREATE INDEX idx_orders_user_created ON orders (user_id, created_at DESC);

# 3. Batch queries instead of N+1
# BAD
for user_id in user_ids:
    orders = await db.fetch("SELECT * FROM orders WHERE user_id = $1", user_id)

# GOOD
orders = await db.fetch(
    "SELECT * FROM orders WHERE user_id = ANY($1::int[])",
    user_ids,
)

# 4. Use server-side cursors for large results
async with pool.acquire() as conn:
    async with conn.transaction():
        async for record in conn.cursor("SELECT * FROM large_table"):
            process(record)

# 5. Connection pool sizing
# Rule of thumb: connections = (2 * CPU cores) + disk spindles
# For cloud: start with 20, adjust based on monitoring
```

## Connection Pooling

```python
# asyncpg pool sizing
pool = await asyncpg.create_pool(
    dsn,
    min_size=10,       # 최소 유지 커넥션
    max_size=50,       # 최대 커넥션 (DB max_connections 고려)
    max_inactive_connection_lifetime=300,  # 유휴 커넥션 정리
    command_timeout=30,
)

# SQLAlchemy async pool
engine = create_async_engine(
    dsn,
    pool_size=20,         # 유지할 커넥션 수
    max_overflow=10,      # pool_size 초과 시 추가 허용
    pool_timeout=30,      # 커넥션 대기 타임아웃
    pool_recycle=3600,    # 커넥션 재생성 주기
    pool_pre_ping=True,   # 커넥션 유효성 사전 체크
)
```

## Common Bottlenecks

```python
# 1. String concatenation in loop → O(n^2)
# BAD
result = ""
for s in strings:
    result += s
# GOOD
result = "".join(strings)

# 2. List comprehension vs generator
# BAD: 전체 리스트 생성 후 합산
total = sum([x ** 2 for x in range(10**7)])  # 80MB 리스트 생성
# GOOD: generator expression (메모리 ~0)
total = sum(x ** 2 for x in range(10**7))

# 3. dict.get() vs try/except for missing keys
# KeyError 빈도 높으면 get()이 빠름
value = d.get(key, default)  # LBYL
# KeyError 빈도 낮으면 try/except가 빠름
try:                          # EAFP
    value = d[key]
except KeyError:
    value = default

# 4. Global variable lookup is slower
# BAD (global lookup each iteration)
import math
def compute(values):
    return [math.sqrt(v) for v in values]

# GOOD (local reference)
def compute(values):
    sqrt = math.sqrt  # local binding
    return [sqrt(v) for v in values]

# 5. set lookup vs list lookup
# BAD: O(n) per lookup
if item in large_list: ...

# GOOD: O(1) per lookup
large_set = set(large_list)
if item in large_set: ...
```

## Benchmarking

```python
# timeit (command line)
# python -m timeit -n 10000 -r 5 "sum(range(1000))"

# Programmatic
import timeit
result = timeit.timeit("sum(range(1000))", number=10000)
print(f"{result:.4f}s for 10000 iterations")

# pytest-benchmark
# pip install pytest-benchmark
def test_sort_performance(benchmark):
    data = list(range(10000, 0, -1))
    result = benchmark(sorted, data)
    assert result == list(range(1, 10001))

# Run: pytest --benchmark-only --benchmark-sort=mean
```
