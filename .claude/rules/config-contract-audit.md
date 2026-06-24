# Config Contract Audit Rules

설정/환경변수/dependency 버전이 시스템 동작을 좌우하는 모든 작업에 적용한다.
**"설정 안 한 것 = 자동으로 처리되니 괜찮다"** 라는 가장 흔한 mental model을 교정한다.

---

## 3단계 검증 (MANDATORY)

설정 항목을 다룰 때 **반드시 아래 3단계 모두 명시적으로 확인**한다. 한 단계라도 생략하면 production 사고로 이어진다.

```
1. 명시값         — 코드/manifest에 직접 적힌 값
   ↓
2. 라이브러리/플랫폼 기본값  — documented default (CHANGELOG, source code 직접 확인)
   ↓
3. 환경별 override — dev/staging/prod에서 다른 값으로 덮어쓰는지
```

- 명시값만 보고 "정상이네" 라고 판단 금지
- 기본값은 **버전 업그레이드 시 변경**된다 (예: OTel exporter protocol gRPC → HTTP)
- 환경별 override는 `application-prod.yml`, `values-prod.yaml`, `.env.prod` 등 분산 — 한 군데만 보면 안 됨

---

## 신규 config 추가 시 3곳 동시 갱신 (MANDATORY)

신규 환경변수 / 설정 키를 추가할 때 반드시 **3곳을 동시 갱신**한다. 어느 하나라도 누락되면 dev에선 동작하다가 prod에서 zero value 발생.

| 갱신 위치 | 누락 시 증상 |
|---------|-------------|
| 1. 구조체/클래스 필드 | 컴파일 통과해도 런타임에 unmapped |
| 2. 기본값 등록 (Viper `SetDefault`, `@Value(":default")`, Helm `default`) | `AutomaticEnv`가 인식 못 함 (Go Viper), null pointer (Spring), empty string |
| 3. 환경별 override 명세 (env file, values-{env}.yaml, ConfigMap) | dev에선 SetDefault에 의존해 동작, prod에선 override 누락 시 빈 값 |

**자주 발생하는 사고 패턴**:
- Go + Viper: `SetDefault` 등록 안 한 key는 `Unmarshal + AutomaticEnv` 조합에서 silent skip
- Spring `@Value`: `${KEY}` 만 적고 default 미지정 시 prod에서 BeanCreationException
- Helm: `values.yaml`에만 추가하고 `values-prod.yaml` 누락 시 prod에서 빈 값

---

## 버전업 시 breaking change 의무 확인 (MANDATORY)

라이브러리/CLI/Helm chart 메이저 또는 마이너 업그레이드 시 **반드시 CHANGELOG breaking change 섹션을 직접 확인**한다.

- WebFetch로 공식 CHANGELOG / migration guide 확인
- 변경된 default 값 식별 — 명시 안 한 값이 silently 바뀜
- config key 이름 변경 / 제거 (예: Mimir `max_write_request_data_item_size` 제거)
- 의존 라이브러리 transitive 버전 강제 다운그레이드 가능성

```
❌ "버전 올려도 동작하니 OK"
⭕ "CHANGELOG breaking change 항목 N개 확인, default 변경 M개 식별"
```

---

## Dependency 관리 (BOM / lock file)

플랫폼이 제공하는 dependency management가 사용자 명시 버전을 덮어쓸 수 있다.

| 사례 | 함정 |
|------|------|
| Spring Boot `dependency-management` | 명시한 OTel 버전을 Spring 관리 버전으로 다운그레이드 |
| Maven/Gradle BOM 충돌 | 여러 BOM 중 마지막이 이긴다 — 순서 의존 |
| `package-lock.json` 미갱신 | `package.json`만 수정해도 실제 설치 안 됨 |

**검증 방법**:
```bash
# 실제 resolved 버전 확인 (Gradle)
./gradlew dependencies --configuration runtimeClasspath | grep <library>

# 실제 resolved 버전 확인 (Maven)
mvn dependency:tree | grep <library>

# 빌드 후 jar 안에 들어간 실제 버전 확인
unzip -l build/libs/*.jar | grep <library>
```

기대 버전 ≠ resolved 버전이면 BOM 통합 또는 `enforcedPlatform` 적용.

---

## DB / managed service config

매니지드 DB(RDS, Cloud SQL 등)의 동작은 self-hosted와 다르다. 묵시적 기본값에 의존하지 않는다.

- **slow query log / general log** — 기본 off, 사고 분석 위해 명시 활성화
- **timezone** — 클러스터/인스턴스 단위 default가 UTC가 아닐 수 있음
- **superuser ≠ documented superuser** (예: Cloud SQL `cloudsqlsuperuser`는 OS-level superuser 아님)
- **search_path** (Postgres) — schema 의존 코드는 `SET search_path TO ...` 명시
- **collation** — 다국어 데이터의 정렬/비교 동작 영향

production 마이그레이션 전 위 항목을 명시적으로 점검.

---

## 환경별 diff 자동화

dev / staging / prod의 manifest / values / env 파일은 **diff 자동화**가 필수다.

```bash
# Helm values diff 예시
diff <(yq '.image' values-dev.yaml) <(yq '.image' values-prod.yaml)

# K8s manifest 환경 비교
diff -r overlays/dev/ overlays/prod/
```

CI 단계에서 환경 간 expected diff(자원 한도, replica 수 등)와 unexpected diff(누락된 env 등)를 자동 검출.

---

## 위반 시 발생하는 실제 사고 패턴

| Mental model 오류 | 실제 사고 |
|------------------|---------|
| "OTel 기본값이 그대로일 것" | exporter protocol gRPC→HTTP 변경, traces 전부 drop |
| "Viper Unmarshal하면 env 자동 바인딩" | SetDefault 안 한 key는 zero value, JWT 검증 실패 |
| "Spring BOM에 적힌 버전이 적용될 것" | dependency-management가 덮어써서 spec 위반 |
| "Helm chart 마이너 업데이트는 안전" | config key 이름 변경, CrashLoopBackOff |
| "Postgres는 다 동일" | Cloud SQL superuser 권한 차이로 extension 설치 실패 |

---

## 자기 점검 체크리스트

config 변경 PR 작성 후 self-review:

- [ ] 명시값 / 기본값 / 환경별 override 3단계 모두 확인했는가?
- [ ] 신규 key는 구조체 + SetDefault + env 명세 3곳에 모두 반영했는가?
- [ ] 라이브러리 버전 변경 시 CHANGELOG breaking change 확인했는가?
- [ ] dev에서 동작 ≠ prod 동작 가능한 차이를 식별했는가?
- [ ] 환경 간 diff 자동화 스크립트가 새 key를 검출하는가?
