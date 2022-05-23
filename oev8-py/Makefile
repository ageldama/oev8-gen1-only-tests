PROTOC = protoc

PROTO_SRC_PATH = ../oev8-protobuf


generate_pb2_pys:
	$(PROTOC) -I $(PROTO_SRC_PATH) --python_out=. ../oev8-protobuf/oev8.proto


lint:
	poetry run pylint oev8/
	poetry run pylint server_app.py
	poetry run flake8 oev8/
	poetry run flake8 server_app.py
	poetry run mypy oev8/
	poetry run mypy server_app.py


test: test-unit test-int test-sys


test-unit:
	poetry run pytest -m 'not int'


test-int:
	poetry run pytest -m 'int'


test-sys:
	OEV8_SYS_TEST=1 poetry run pytest ./test/system_tests


.PHONY: test test-unit test-int test-sys lint


all: generate_pb2_pys
