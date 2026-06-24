---
name: python-testing
description: "Python Testing Patterns — pytest 기반 테스트 전략. 단위/통합/E2E 테스트와 async 테스트 패턴. Use when working with python 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Python Testing Patterns

pytest 기반 테스트 전략. 단위/통합/E2E 테스트와 async 테스트 패턴.

## Quick Reference

```
테스트 프레임워크 선택?
├── 단위 테스트 ────────> pytest + fixtures
├── Mock/Stub ─────────> unittest.mock / pytest-mock
├── Async 테스트 ──────> pytest-asyncio
├── API 테스트 ────────> httpx.AsyncClient / TestClient
├── DB 통합 테스트 ────> testcontainers-python
├── 속성 기반 ─────────> hypothesis
└── 커버리지 ──────────> pytest-cov

fixture scope 선택?
├── 테스트마다 격리 ───> function (default)
├── 클래스 내 공유 ────> class
├── 모듈 내 공유 ──────> module
└── 전체 세션 공유 ────> session (DB 초기화 등)
```

---

## pytest Basics

### Fixtures

```python
import pytest

@pytest.fixture
def user() -> User:
    return User(name="Alice", email="alice@test.com")

@pytest.fixture
def admin_user() -> User:
    return User(name="Admin", email="admin@test.com", is_admin=True)

# Fixture with setup/teardown
@pytest.fixture
def tmp_database(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    db.create_tables()
    yield db
    db.close()

# Shared fixtures: conftest.py (auto-discovered by pytest)
# tests/conftest.py
@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
```

### Parametrize

```python
@pytest.mark.parametrize("input_val,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_to_upper(input_val: str, expected: str):
    assert to_upper(input_val) == expected

# Multiple parameter sets with IDs
@pytest.mark.parametrize("email,is_valid", [
    ("user@example.com", True),
    ("invalid", False),
    ("@no-user.com", False),
    ("user@.com", False),
], ids=["valid_email", "no_at_sign", "no_username", "no_domain"])
def test_email_validation(email: str, is_valid: bool):
    assert validate_email(email) == is_valid

# Parametrize with fixtures
@pytest.mark.parametrize("role,expected_status", [
    ("admin", 200),
    ("user", 403),
    ("guest", 401),
])
async def test_admin_endpoint(client, role, expected_status):
    token = create_token(role=role)
    response = await client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == expected_status
```

### Markers

```python
# pyproject.toml
# [tool.pytest.ini_options]
# markers = [
#     "slow: marks tests as slow",
#     "integration: integration tests",
#     "e2e: end-to-end tests",
# ]

@pytest.mark.slow
def test_large_data_processing():
    ...

@pytest.mark.integration
def test_database_connection():
    ...

# Run specific markers
# pytest -m "not slow"
# pytest -m "integration"
```

## Mocking

### unittest.mock

```python
from unittest.mock import MagicMock, AsyncMock, patch, call

# Patching a module-level function
@patch("app.services.user_service.send_email")
def test_should_send_welcome_email(mock_send: MagicMock):
    # Given
    user = User(email="test@test.com", name="Test")

    # When
    UserService.register(user)

    # Then
    mock_send.assert_called_once_with(
        to="test@test.com",
        template="welcome",
        context={"name": "Test"},
    )

# Patching with return value
@patch("app.repositories.user_repo.UserRepo.find_by_id")
def test_should_return_user(mock_find: MagicMock):
    # Given
    mock_find.return_value = User(id=1, name="Alice")

    # When
    result = UserService.get_user(1)

    # Then
    assert result.name == "Alice"
    mock_find.assert_called_once_with(1)

# Async mock
@patch("app.services.payment_service.charge", new_callable=AsyncMock)
async def test_should_charge_payment(mock_charge: AsyncMock):
    mock_charge.return_value = PaymentResult(success=True, tx_id="abc")

    result = await OrderService.process_payment(order_id=1, amount=5000)

    assert result.success is True
    mock_charge.assert_awaited_once()
```

### pytest-mock

```python
def test_with_mocker(mocker):
    # mocker is a fixture from pytest-mock
    mock_repo = mocker.patch("app.services.UserRepo")
    mock_repo.return_value.find_by_id.return_value = User(id=1, name="Alice")

    result = UserService.get_user(1)
    assert result.name == "Alice"

# Spy: call original but track calls
def test_with_spy(mocker):
    spy = mocker.spy(UserService, "validate_email")

    UserService.register(email="test@test.com", name="Test")

    spy.assert_called_once_with("test@test.com")
```

## Async Testing

```python
import pytest
import pytest_asyncio

# pyproject.toml: asyncio_mode = "auto"

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session
        await session.rollback()

async def test_should_create_user(async_client: AsyncClient):
    # Given
    payload = {"email": "new@test.com", "name": "New User", "password": "StrongP4ss"}

    # When
    response = await async_client.post("/users/", json=payload)

    # Then
    assert response.status_code == 201

async def test_should_fetch_concurrently(db_session):
    # Given
    users = [User(name=f"user_{i}") for i in range(10)]
    db_session.add_all(users)
    await db_session.flush()

    # When
    results = await UserService.fetch_batch([u.id for u in users])

    # Then
    assert len(results) == 10
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures (db, client, factories)
├── unit/
│   ├── conftest.py
│   ├── test_user_service.py
│   └── test_order_service.py
├── integration/
│   ├── conftest.py          # DB setup fixtures
│   ├── test_user_repo.py
│   └── test_payment_gateway.py
└── e2e/
    ├── conftest.py          # Full app fixtures
    └── test_order_flow.py
```

### conftest.py Patterns

```python
# tests/conftest.py — root level shared fixtures

@pytest.fixture(scope="session")
def event_loop():
    """Override default event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    async with async_sessionmaker(db_engine)() as session:
        yield session
        await session.rollback()
```

## Integration Testing with Testcontainers

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture(scope="session")
def db_url(postgres) -> str:
    return postgres.get_connection_url()

def test_user_repository(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    repo = UserRepository(engine)

    # Given
    user = User(name="Test", email="test@test.com")

    # When
    created = repo.create(user)

    # Then
    found = repo.find_by_id(created.id)
    assert found.email == "test@test.com"
```

## Coverage

```toml
# pyproject.toml
[tool.coverage.run]
source = ["app"]
branch = true
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

```bash
# Run with coverage
pytest --cov=app --cov-report=term-missing --cov-report=html

# Branch coverage
pytest --cov=app --cov-branch
```

## Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st, settings

@given(st.text(min_size=1, max_size=100))
def test_slugify_never_empty(text: str):
    result = slugify(text)
    # Slug should only contain valid chars
    assert all(c.isalnum() or c == "-" for c in result)

@given(
    st.integers(min_value=1, max_value=1000),
    st.integers(min_value=1, max_value=1000),
)
def test_calculate_total_positive(quantity: int, price: int):
    total = calculate_total(quantity, price)
    assert total > 0
    assert total == quantity * price

@given(st.emails())
@settings(max_examples=200)
def test_email_validation_handles_all(email: str):
    # Should not raise any exception
    result = validate_email(email)
    assert isinstance(result, bool)
```

## Best Practices

```python
# 1. One assertion concept per test
# BAD
def test_user():
    user = create_user("test")
    assert user.name == "test"
    assert user.is_active
    assert user.orders == []
    assert user.email is None  # testing too many things

# GOOD: focused tests
def test_should_create_user_with_name():
    user = create_user("test")
    assert user.name == "test"

def test_new_user_should_be_active():
    user = create_user("test")
    assert user.is_active is True

# 2. Use factories for test data
class UserFactory:
    @staticmethod
    def create(**overrides) -> User:
        defaults = {
            "name": "Test User",
            "email": "test@test.com",
            "status": "active",
        }
        return User(**(defaults | overrides))

# 3. Freeze time for deterministic tests
from freezegun import freeze_time

@freeze_time("2025-01-01 12:00:00")
def test_should_calculate_age():
    user = User(birth_date=date(2000, 1, 1))
    assert user.age == 25

# 4. Custom assertion helpers
def assert_user_response(data: dict, expected_user: User) -> None:
    assert data["id"] == expected_user.id
    assert data["email"] == expected_user.email
    assert "password" not in data  # security check
```

## CI Integration

```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_PASSWORD: test
      ports: ["5432:5432"]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: pip install -r requirements-test.txt
    - run: pytest --cov=app --cov-report=xml -x
    - uses: codecov/codecov-action@v4
```
