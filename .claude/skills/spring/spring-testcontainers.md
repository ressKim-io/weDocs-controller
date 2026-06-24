---
name: spring-testcontainers
description: "Spring Testcontainers Patterns — Testcontainers, REST Assured를 활용한 통합 테스트 패턴 Use when working with spring 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Spring Testcontainers Patterns

Testcontainers, REST Assured를 활용한 통합 테스트 패턴

## Quick Reference (결정 트리)

```
통합 테스트 대상
    │
    ├─ PostgreSQL ────> PostgreSQLContainer
    │
    ├─ MongoDB ───────> MongoDBContainer
    │
    ├─ Redis ─────────> GenericContainer("redis:7")
    │
    └─ API 테스트 ────> REST Assured + @SpringBootTest
```

---

## 의존성

```groovy
dependencies {
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.testcontainers:junit-jupiter'
    testImplementation 'org.testcontainers:postgresql'
    testImplementation 'org.testcontainers:mongodb'
    testImplementation 'io.rest-assured:rest-assured'
}
```

---

## CRITICAL: 공유 컨테이너 설정

**IMPORTANT**: 컨테이너 재사용으로 테스트 속도 향상

```java
@SpringBootTest
@Testcontainers
public abstract class IntegrationTestBase {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("testdb")
        .withReuse(true);  // 컨테이너 재사용

    @Container
    static GenericContainer<?> redis = new GenericContainer<>("redis:7")
        .withExposedPorts(6379)
        .withReuse(true);

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.data.redis.host", redis::getHost);
        registry.add("spring.data.redis.port", () -> redis.getMappedPort(6379));
    }
}

// 사용
class UserIntegrationTest extends IntegrationTestBase {
    @Test
    void integrationTest() {
        // 테스트 로직
    }
}
```

---

## PostgreSQL + @DataJpaTest

```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
@Testcontainers
class UserRepositoryTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private UserRepository userRepository;

    @Test
    void findByEmail_Success() {
        User user = User.builder().email("test@example.com").build();
        userRepository.save(user);

        Optional<User> found = userRepository.findByEmail("test@example.com");
        assertThat(found).isPresent();
    }
}
```

---

## MongoDB

```java
@DataMongoTest
@Testcontainers
class ProductRepositoryTest {

    @Container
    static MongoDBContainer mongo = new MongoDBContainer("mongo:6");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.data.mongodb.uri", mongo::getReplicaSetUrl);
    }

    @Autowired
    private ProductRepository productRepository;

    @Test
    void findByCategory() {
        productRepository.save(new Product("Test", "Electronics", 100.0));

        List<Product> found = productRepository.findByCategory("Electronics");
        assertThat(found).hasSize(1);
    }
}
```

---

## REST Assured (API 테스트)

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class UserApiTest extends IntegrationTestBase {

    @LocalServerPort
    private int port;

    @BeforeEach
    void setup() {
        RestAssured.port = port;
        RestAssured.basePath = "/api";
    }

    @Test
    void createAndGetUser() {
        // Create
        CreateUserRequest request = new CreateUserRequest("api@example.com", "password");

        UserResponse created = given()
            .contentType(ContentType.JSON)
            .body(request)
        .when()
            .post("/users")
        .then()
            .statusCode(201)
            .extract()
            .as(UserResponse.class);

        assertThat(created.getId()).isNotNull();

        // Get
        given()
        .when()
            .get("/users/{id}", created.getId())
        .then()
            .statusCode(200)
            .body("email", equalTo("api@example.com"));
    }

    @Test
    void authenticatedEndpoint() {
        String token = obtainAccessToken("user@example.com", "password");

        given()
            .header("Authorization", "Bearer " + token)
        .when()
            .get("/users/me")
        .then()
            .statusCode(200);
    }
}
```

---

## @Sql 테스트 데이터

```java
@Test
@Sql("/sql/users.sql")
@Sql(value = "/sql/cleanup.sql", executionPhase = AFTER_TEST_METHOD)
void testWithPreparedData() {
    List<User> users = userRepository.findAll();
    assertThat(users).hasSize(5);
}
```

---

## 컨테이너 재사용 설정

`~/.testcontainers.properties`:
```properties
testcontainers.reuse.enable=true
```

**효과**: 테스트 실행 시 기존 컨테이너 재사용 → 속도 향상

---

## Anti-Patterns

| 실수 | 올바른 방법 |
|------|------------|
| 매 테스트마다 컨테이너 생성 | `withReuse(true)` + 공유 Base |
| 하드코딩된 포트 | `getMappedPort()` 사용 |
| 테스트 후 데이터 남김 | @Sql cleanup 또는 @Transactional |
| H2 대신 실제 DB 안 씀 | Testcontainers로 실제 DB 테스트 |

---

## 체크리스트

- [ ] 공유 컨테이너 Base 클래스 생성
- [ ] `withReuse(true)` 설정
- [ ] `@DynamicPropertySource`로 설정 주입
- [ ] 테스트 데이터 정리 전략
- [ ] CI에서 Docker 사용 가능 확인
