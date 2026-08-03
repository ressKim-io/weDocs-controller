# weDocs-controller — proto SSOT 편의 명령
# 사용: make <target>

.PHONY: proto-lint proto-breaking proto-gen proto-doc proto-format help

PROTO_DIR := proto

## proto-lint: buf lint 실행
proto-lint:
	buf lint $(PROTO_DIR)

## proto-format: buf format (check)
proto-format:
	buf format $(PROTO_DIR) -d --exit-code

## proto-format-fix: buf format (write)
proto-format-fix:
	buf format $(PROTO_DIR) -w

## proto-breaking: main 대비 wire 호환성 검사
proto-breaking:
	buf breaking $(PROTO_DIR) --against '.git#branch=main,subdir=$(PROTO_DIR)'

## proto-gen: 3언어 코드 생성 (검증용, gen/ gitignored)
proto-gen:
	buf generate

## proto-doc: gRPC API 문서 생성 → docs/proto/api-reference.md
proto-doc:
	buf generate --template buf.gen.doc.yaml

## proto-check: lint + breaking + doc freshness 일괄 검증
proto-check: proto-lint proto-breaking proto-doc
	@git diff --quiet docs/proto/ || (echo "ERROR: docs/proto/ is out of date. Run 'make proto-doc' and commit." && exit 1)

## help: 사용 가능한 타겟 목록
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //' | column -t -s ':'
