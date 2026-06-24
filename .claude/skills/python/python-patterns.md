---
name: python-patterns
description: "Python Design Patterns — 타입 힌트, 디자인 패턴, Clean Architecture, SOLID 원칙의 Python 구현 가이드. Use when working with python 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Python Design Patterns

타입 힌트, 디자인 패턴, Clean Architecture, SOLID 원칙의 Python 구현 가이드.

## Quick Reference

```
패턴 선택?
├── 데이터 모델링 ──────> dataclass / Pydantic
├── 인터페이스 정의 ────> Protocol / ABC
├── 의존성 주입 ────────> 생성자 주입 + Protocol
├── 리소스 관리 ────────> Context Manager
├── 횡단 관심사 ────────> Decorator
├── 값 분기 처리 ───────> match/case (3.10+)
├── 제네릭 타입 ────────> TypeVar + Generic
└── 전략 교체 ─────────> Strategy pattern

데이터 클래스 선택?
├── 단순 데이터 홀더 ──> dataclass
├── 입력 검증 필요 ────> Pydantic BaseModel
├── 불변 데이터 ───────> dataclass(frozen=True) / NamedTuple
├── 성능 중요 ─────────> dataclass + __slots__
└── JSON 직렬화 ───────> Pydantic BaseModel
```

---

## Type Hints (Modern Python 3.10+)

### Generics and TypeVar

```python
from typing import TypeVar, Generic
from collections.abc import Sequence

T = TypeVar("T")

class Repository(Generic[T]):
    def __init__(self, model_class: type[T]) -> None:
        self._model = model_class
        self._items: list[T] = []

    def add(self, item: T) -> None:
        self._items.append(item)

    def find_by_id(self, id: int) -> T | None:
        return next((item for item in self._items if item.id == id), None)

    def find_all(self) -> list[T]:
        return list(self._items)

# Usage
user_repo = Repository[User](User)
user_repo.add(User(id=1, name="Alice"))
```

### Protocol (Structural Typing)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Sendable(Protocol):
    def send(self, message: str) -> bool: ...

class EmailSender:
    def send(self, message: str) -> bool:
        # 이메일 전송 구현
        return True

class SlackSender:
    def send(self, message: str) -> bool:
        # Slack 전송 구현
        return True

# Protocol을 만족하면 명시적 상속 없이 사용 가능
def notify(sender: Sendable, message: str) -> bool:
    return sender.send(message)

notify(EmailSender(), "hello")  # OK
notify(SlackSender(), "hello")  # OK
assert isinstance(EmailSender(), Sendable)  # True (runtime_checkable)
```

### ParamSpec (Decorator typing)

```python
from typing import ParamSpec, TypeVar
from collections.abc import Callable
from functools import wraps

P = ParamSpec("P")
R = TypeVar("R")

def retry(max_attempts: int = 3) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
            raise RuntimeError("Unreachable")
        return wrapper
    return decorator

@retry(max_attempts=3)
def fetch_data(url: str, timeout: int = 30) -> dict:
    ...
# fetch_data의 타입 시그니처가 그대로 유지됨
```

## dataclass vs Pydantic

```python
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, ConfigDict

# dataclass: 단순 데이터 홀더 (검증 없음)
@dataclass
class Point:
    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

# dataclass + __slots__: 메모리 효율
@dataclass(slots=True, frozen=True)
class ImmutablePoint:
    x: float
    y: float

# Pydantic: 입력 검증 + 직렬화
class UserCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int = Field(ge=0, le=150)

# 선택 기준:
# - 내부 도메인 객체 → dataclass (빠름, 심플)
# - API 입출력, 외부 데이터 → Pydantic (검증, 직렬화)
# - 불변 값 객체 → dataclass(frozen=True) or NamedTuple
```

## Design Patterns

### Repository Pattern

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")

class BaseRepository(ABC, Generic[T]):
    @abstractmethod
    async def find_by_id(self, id: int) -> T | None: ...

    @abstractmethod
    async def find_all(self, offset: int = 0, limit: int = 100) -> list[T]: ...

    @abstractmethod
    async def save(self, entity: T) -> T: ...

    @abstractmethod
    async def delete(self, id: int) -> bool: ...

class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, id: int) -> User | None:
        return await self._session.get(User, id)

    async def find_all(self, offset: int = 0, limit: int = 100) -> list[User]:
        stmt = select(User).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, entity: User) -> User:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, id: int) -> bool:
        user = await self.find_by_id(id)
        if user:
            await self._session.delete(user)
            return True
        return False
```

### Unit of Work Pattern

```python
class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> "UnitOfWork":
        self._session = self._session_factory()
        self.users = UserRepository(self._session)
        self.orders = OrderRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

# Usage
async def transfer_order(uow_factory, user_id: int, order_data: dict) -> Order:
    async with uow_factory() as uow:
        user = await uow.users.find_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        order = Order(user_id=user.id, **order_data)
        await uow.orders.save(order)
        await uow.commit()
        return order
```

### Strategy Pattern

```python
from typing import Protocol

class PricingStrategy(Protocol):
    def calculate(self, base_price: float, quantity: int) -> float: ...

class RegularPricing:
    def calculate(self, base_price: float, quantity: int) -> float:
        return base_price * quantity

class BulkPricing:
    def __init__(self, threshold: int = 10, discount: float = 0.1) -> None:
        self._threshold = threshold
        self._discount = discount

    def calculate(self, base_price: float, quantity: int) -> float:
        total = base_price * quantity
        if quantity >= self._threshold:
            total *= (1 - self._discount)
        return total

class SeasonalPricing:
    def __init__(self, multiplier: float = 1.2) -> None:
        self._multiplier = multiplier

    def calculate(self, base_price: float, quantity: int) -> float:
        return base_price * quantity * self._multiplier

class OrderService:
    def __init__(self, pricing: PricingStrategy) -> None:
        self._pricing = pricing

    def calculate_total(self, base_price: float, quantity: int) -> float:
        return self._pricing.calculate(base_price, quantity)

# Usage
service = OrderService(BulkPricing(threshold=5, discount=0.15))
total = service.calculate_total(100.0, 10)
```

## Dependency Injection

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, id: int) -> User | None: ...
    async def save(self, user: User) -> User: ...

class NotificationService(Protocol):
    async def notify(self, user: User, message: str) -> None: ...

# Constructor injection
class UserService:
    def __init__(
        self,
        repo: UserRepository,
        notifier: NotificationService,
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def register(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        saved = await self._repo.save(user)
        await self._notifier.notify(saved, "Welcome!")
        return saved

# Composition root (FastAPI example)
def create_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(
        repo=SqlUserRepository(db),
        notifier=EmailNotificationService(),
    )

@router.post("/users")
async def register(
    data: UserCreate,
    service: UserService = Depends(create_user_service),
) -> UserResponse:
    return await service.register(data)
```

## Context Managers

```python
from contextlib import contextmanager, asynccontextmanager

# Sync context manager
@contextmanager
def timer(label: str):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.info("%s took %.3fs", label, elapsed)

with timer("data processing"):
    process_data()

# Async context manager
@asynccontextmanager
async def db_transaction(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise

async with db_transaction(pool) as conn:
    await conn.execute("INSERT INTO users ...")
```

## Decorators

```python
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

# Function decorator with arguments
def cache(ttl: int = 300):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        _cache: dict[str, tuple[float, R]] = {}

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = f"{args}:{kwargs}"
            now = time.time()
            if key in _cache:
                cached_time, value = _cache[key]
                if now - cached_time < ttl:
                    return value
            result = func(*args, **kwargs)
            _cache[key] = (now, result)
            return result
        return wrapper
    return decorator

@cache(ttl=60)
def expensive_computation(x: int) -> int:
    return x ** 2

# Class decorator
def singleton(cls):
    instances: dict[type, Any] = {}

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance
```

## Structural Pattern Matching (Python 3.10+)

```python
def process_event(event: dict) -> str:
    match event:
        case {"type": "click", "element": str(elem)}:
            return f"Clicked on {elem}"
        case {"type": "error", "code": int(code)} if code >= 500:
            return f"Server error: {code}"
        case {"type": "error", "code": int(code)}:
            return f"Client error: {code}"
        case _:
            return "Unknown event"

# match with dataclasses
@dataclass
class CreateUser:
    name: str
    email: str

@dataclass
class DeleteUser:
    user_id: int

def handle_command(cmd) -> str:
    match cmd:
        case CreateUser(name=name, email=email):
            return f"Creating user {name} ({email})"
        case DeleteUser(user_id=uid):
            return f"Deleting user {uid}"
```

## SOLID in Python

```python
# Single Responsibility: 하나의 책임만
class UserValidator:
    def validate(self, data: UserCreate) -> list[str]: ...

class UserRepository:
    async def save(self, user: User) -> User: ...

class UserNotifier:
    async def send_welcome(self, user: User) -> None: ...

# Open/Closed: Protocol + Strategy로 확장
class Exporter(Protocol):
    def export(self, data: list[dict]) -> bytes: ...

class CsvExporter:
    def export(self, data: list[dict]) -> bytes: ...

class JsonExporter:
    def export(self, data: list[dict]) -> bytes: ...

# Liskov Substitution: Protocol 준수
# Interface Segregation: 작은 Protocol 단위
class Readable(Protocol):
    async def read(self, id: int) -> dict | None: ...

class Writable(Protocol):
    async def write(self, data: dict) -> int: ...

# Dependency Inversion: 고수준이 저수준에 의존하지 않음
class OrderService:
    def __init__(self, repo: Readable, notifier: Sendable) -> None: ...
```

## Clean Architecture Layers

```
Entities (Domain)      순수 비즈니스 로직, 외부 의존성 없음
  ↑
Use Cases (Services)   애플리케이션 로직, Protocol로 인프라 추상화
  ↑
Adapters (Repos, API)  DB, HTTP, 메시지큐 등 구현
  ↑
Frameworks (FastAPI)   프레임워크 설정, DI 구성
```

```python
# Domain (no imports from frameworks)
@dataclass
class Order:
    id: int
    user_id: int
    total: float
    status: str = "pending"

    def confirm(self) -> None:
        if self.status != "pending":
            raise DomainError(f"Cannot confirm order in {self.status} status")
        self.status = "confirmed"

# Use case (depends only on Protocols)
class ConfirmOrderUseCase:
    def __init__(self, repo: OrderRepository, notifier: Notifier) -> None:
        self._repo = repo
        self._notifier = notifier

    async def execute(self, order_id: int) -> Order:
        order = await self._repo.find_by_id(order_id)
        if not order:
            raise NotFoundError("Order", order_id)
        order.confirm()
        await self._repo.save(order)
        return order
```
