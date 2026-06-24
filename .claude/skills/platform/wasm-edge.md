---
name: wasm-edge
description: "WebAssembly Edge 가이드 — WASM/WASI, WasmEdge, Spin, Kubernetes WASM 워크로드 실행 Use when working with platform 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# WebAssembly Edge 가이드

WASM/WASI, WasmEdge, Spin, Kubernetes WASM 워크로드 실행

## Quick Reference (결정 트리)

```
WASM 런타임 선택?
    |
    +-- 범용 (서버, CLI, IoT) ------> WasmEdge
    |       |
    |       +-- Kubernetes 통합 ----> WasmEdge + runwasi
    |       +-- AI 추론 ------------> WasmEdge GGML 플러그인
    |
    +-- Serverless 함수 ------------> Spin (Fermyon)
    |       |
    |       +-- Kubernetes 배포 ----> Spin Operator
    |       +-- 클라우드 관리형 ----> Fermyon Cloud
    |
    +-- 브라우저 확장 --------------> wasm-bindgen
    |
    +-- 경량 컨테이너 대안 ---------> Kubernetes + runwasi

WASM vs Container?
    |
    +-- 시작 시간 중요 (μs) --------> WASM
    +-- 크기 중요 (MB → KB) --------> WASM
    +-- 기존 생태계 필요 -----------> Container
    +-- 복잡한 시스템 콜 -----------> Container
```

---

## CRITICAL: WASM vs Container 비교

| 항목 | WASM | Container |
|------|------|-----------|
| **시작 시간** | μs (마이크로초) | 초 단위 |
| **이미지 크기** | KB ~ 수 MB | 수십 ~ 수백 MB |
| **메모리** | 매우 적음 | 기본 오버헤드 |
| **보안** | 샌드박스 격리 | 커널 공유 |
| **언어 지원** | Rust, C/C++, Go, JS | 모든 언어 |
| **시스템 접근** | WASI 통해 제한적 | 전체 커널 접근 |
| **이식성** | 완전 (아키텍처 무관) | 아키텍처별 빌드 |
| **성숙도** | 발전 중 | 검증됨 |

### WASM 적합 사례

```
+-- 엣지/IoT 디바이스
|   +-- 제한된 리소스
|   +-- 빠른 시작 필요
|
+-- Serverless 함수
|   +-- Cold start 최소화
|   +-- 비용 효율 (ms 단위 과금)
|
+-- 플러그인 시스템
|   +-- 안전한 확장
|   +-- 언어 무관 통합
|
+-- CDN/Edge Computing
    +-- 글로벌 배포
    +-- 초저지연
```

---

## WASM/WASI 기초

### WASI 로드맵

```
WASI Preview 1 (현재 안정)
    +-- 파일 시스템 기본 접근
    +-- 환경 변수
    +-- 명령줄 인자
    +-- 클럭/시간

WASI Preview 2 (진행 중)
    +-- Component Model
    +-- 비동기 I/O
    +-- HTTP
    +-- 소켓

WASI Preview 3 → 1.0 (2026년 중반 목표)
    +-- 완전한 Component Model
    +-- 표준화된 인터페이스
```

### Component Model

```
+------------------------------------------------------------------+
|                     Component Model                                |
+------------------------------------------------------------------+
|                                                                    |
|  +-------------+              +-------------+                      |
|  | Component A |  <--WIT-->  | Component B |                      |
|  | (Rust)      |  Interface  | (Go)        |                      |
|  +-------------+              +-------------+                      |
|                                                                    |
|  WIT (WebAssembly Interface Types):                                |
|  - 언어 중립 인터페이스 정의                                        |
|  - 컴포넌트 간 통신 규약                                           |
|  - 타입 안전한 바인딩                                              |
|                                                                    |
+------------------------------------------------------------------+
```

### Rust로 WASM 빌드

```rust
// src/main.rs
use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();

    let result = process_data(&input);
    println!("{}", result);
}

fn process_data(data: &str) -> String {
    // 비즈니스 로직
    format!("Processed: {}", data.len())
}
```

```bash
# WASI 타겟으로 빌드
rustup target add wasm32-wasip1
cargo build --target wasm32-wasip1 --release

# 결과: target/wasm32-wasip1/release/myapp.wasm (KB 단위!)
```

---

## WasmEdge

### 개요

WasmEdge는 CNCF 프로젝트로, 클라우드 네이티브, 엣지, 서버리스 환경을 위한 고성능 WASM 런타임입니다.

### 설치

```bash
# 설치 스크립트
curl -sSf https://raw.githubusercontent.com/WasmEdge/WasmEdge/master/utils/install.sh | bash

# 버전 확인
wasmedge --version
```

### 기본 실행

```bash
# WASM 모듈 실행
wasmedge myapp.wasm

# 환경 변수 전달
wasmedge --env KEY=value myapp.wasm

# 파일 시스템 매핑
wasmedge --dir /app:/host/path myapp.wasm
```

### 플러그인 시스템

```bash
# AI 추론 플러그인 (GGML/LLM)
wasmedge --dir .:. \
  wasmedge-ggml-llama.wasm \
  --prompt "Hello, how are you?"

# HTTP 플러그인
wasmedge --dir .:. http-server.wasm

# 데이터베이스 플러그인 (SQLite)
wasmedge --dir .:. database-app.wasm
```

### HTTP 서버 예제 (Rust + WasmEdge)

```rust
// Cargo.toml
[dependencies]
wasmedge-wasi-socket = "0.5"
serde_json = "1.0"

// src/main.rs
use wasmedge_wasi_socket::{Socket, SocketType};
use std::io::{Read, Write};

fn main() {
    let socket = Socket::new(SocketType::Stream).unwrap();
    socket.bind("0.0.0.0:8080").unwrap();
    socket.listen(128).unwrap();

    println!("Server running on :8080");

    loop {
        let mut client = socket.accept().unwrap();
        let mut buffer = [0u8; 4096];
        let n = client.read(&mut buffer).unwrap();

        let response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nHello from WASM!";
        client.write_all(response.as_bytes()).unwrap();
    }
}
```

---

## Spin (Fermyon)

### 개요

Spin은 Fermyon의 WebAssembly 기반 마이크로서비스 프레임워크로, 서버리스 함수를 쉽게 개발하고 배포할 수 있습니다.

### 설치

```bash
# Spin CLI 설치
curl -fsSL https://developer.fermyon.com/downloads/install.sh | bash
sudo mv spin /usr/local/bin/

# 확인
spin --version
```

### 새 프로젝트 생성

```bash
# Rust HTTP 트리거
spin new -t http-rust my-spin-app
cd my-spin-app

# 프로젝트 구조
# ├── spin.toml
# └── src/
#     └── lib.rs
```

### spin.toml 설정

```toml
spin_manifest_version = 2

[application]
name = "my-spin-app"
version = "0.1.0"
description = "My first Spin application"

[[trigger.http]]
route = "/api/..."
component = "my-component"

[component.my-component]
source = "target/wasm32-wasip1/release/my_spin_app.wasm"
allowed_outbound_hosts = ["https://api.example.com"]

[component.my-component.build]
command = "cargo build --target wasm32-wasip1 --release"
watch = ["src/**/*.rs", "Cargo.toml"]
```

### HTTP 핸들러 (Rust)

```rust
// src/lib.rs
use spin_sdk::http::{IntoResponse, Request, Response};
use spin_sdk::http_component;
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct RequestBody {
    name: String,
}

#[derive(Serialize)]
struct ResponseBody {
    message: String,
}

#[http_component]
fn handle_request(req: Request) -> anyhow::Result<impl IntoResponse> {
    let method = req.method();
    let path = req.path();

    match (method.as_str(), path) {
        ("GET", "/api/hello") => {
            let body = ResponseBody {
                message: "Hello from WASM!".to_string(),
            };
            Ok(Response::builder()
                .status(200)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&body)?)
                .build())
        }
        ("POST", "/api/greet") => {
            let body: RequestBody = serde_json::from_slice(req.body())?;
            let response = ResponseBody {
                message: format!("Hello, {}!", body.name),
            };
            Ok(Response::builder()
                .status(200)
                .header("content-type", "application/json")
                .body(serde_json::to_string(&response)?)
                .build())
        }
        _ => Ok(Response::builder().status(404).build()),
    }
}
```

### 로컬 실행 및 배포

```bash
# 빌드
spin build

# 로컬 실행
spin up

# Fermyon Cloud 배포
spin deploy

# OCI 레지스트리에 푸시
spin registry push ghcr.io/myorg/my-spin-app:v1
```

---

## Kubernetes WASM 통합

### runwasi (containerd shim)

```yaml
# RuntimeClass 정의
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: wasmtime
handler: wasmtime
---
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: wasmedge
handler: wasmedge
```

### WASM Pod 실행

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: wasm-app
spec:
  runtimeClassName: wasmedge  # WASM 런타임 사용
  containers:
    - name: app
      image: ghcr.io/myorg/my-wasm-app:v1
      ports:
        - containerPort: 8080
      resources:
        requests:
          cpu: 10m     # 매우 적은 CPU
          memory: 16Mi # 매우 적은 메모리
        limits:
          cpu: 100m
          memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: wasm-app
spec:
  selector:
    app: wasm-app
  ports:
    - port: 80
      targetPort: 8080
```

### Spin Operator (Kubernetes)

```bash
# Spin Operator 설치
kubectl apply -f https://github.com/spinkube/spin-operator/releases/download/v0.4.0/spin-operator.crds.yaml
kubectl apply -f https://github.com/spinkube/spin-operator/releases/download/v0.4.0/spin-operator.runtime-class.yaml
kubectl apply -f https://github.com/spinkube/spin-operator/releases/download/v0.4.0/spin-operator.shim-executor.yaml
```

```yaml
# SpinApp CRD
apiVersion: core.spinoperator.dev/v1alpha1
kind: SpinApp
metadata:
  name: my-spin-app
spec:
  image: ghcr.io/myorg/my-spin-app:v1
  replicas: 3
  executor: containerd-shim-spin

  # 환경 변수
  variables:
    - name: LOG_LEVEL
      value: "info"

  # 자동 스케일링
  enableAutoscaling: true
  targetCPU: 50

  # 리소스
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
    limits:
      cpu: 100m
      memory: 128Mi
```

### Kwasm (Kubernetes WASM Operator)

```bash
# Kwasm 설치
helm repo add kwasm https://kwasm.sh/kwasm-operator/
helm install kwasm-operator kwasm/kwasm-operator \
  --namespace kwasm \
  --create-namespace

# 노드 어노테이션으로 WASM 활성화
kubectl annotate node my-node kwasm.sh/kwasm-node=true
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 모든 워크로드에 WASM | 복잡한 앱에 부적합 | 적합한 사례 선별 |
| WASI 제한 무시 | 런타임 에러 | 지원 기능 확인 |
| 큰 의존성 사용 | WASM 크기 증가 | 경량 라이브러리 선택 |
| 컨테이너 리소스 그대로 | 낭비 | WASM용 최적화 |

---

## 체크리스트

### WASM 기초
- [ ] Rust wasm32-wasip1 타겟 설치
- [ ] WasmEdge 또는 Spin 설치
- [ ] 빌드 파이프라인 구성

### Kubernetes 통합
- [ ] RuntimeClass 설정
- [ ] runwasi 또는 Spin Operator 설치
- [ ] WASM 이미지 레지스트리 준비

**관련 skill**: `/docker`, `/k8s-scheduling`, `/finops`

---

## 참조 스킬

- `wasm-edge-iot.md` - Edge/IoT 활용 사례, 성능 최적화, AOT 컴파일
- `/docker` - 컨테이너 비교
- `/k8s-scheduling` - 워크로드 스케줄링
- `/finops` - 비용 최적화
