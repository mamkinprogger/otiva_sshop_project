import hashlib
import json

import pytest
from django.test import AsyncRequestFactory

import main.utils as utils
from main.utils import LoadTestMixin

@pytest.fixture
def loadtest_hash(monkeypatch):
    monkeypatch.setattr(
        utils,
        "LOADTEST_HASH",
        hashlib.sha256("123".encode()).digest()
    )


class TestLoadTestMixin:
    def test_successful_auth(self, loadtest_hash):
        assert LoadTestMixin().check_auth("123")

    def test_failed_auth(self, loadtest_hash):
        assert not LoadTestMixin().check_auth("1123")
        assert not LoadTestMixin().check_auth(" ")

    def test_no_token_passed(self):
        assert not LoadTestMixin().check_auth(None)

    @pytest.mark.parametrize("body, expect", [
        ({"sql_query": "Select * from db"}, ('Select * from db', [])),
        ({"sql_query": "Select * from db", "sql_params": ["pipka"]}, ('Select * from db', ["pipka"])),
        ({"sql_query": "select 'he'", "sql_params": ["pipka"]}, ("select 'he'", ["pipka"])),
        ({"sql_query": "select 'he'", "sql_params": {"a": "pipka"}}, ("select 'he'", {"a": "pipka"}))
    ], ids=["No params", "With params", "With any char", "Dict params"])
    def test_success_valid_body(self, body, expect):
        request = AsyncRequestFactory().post("/", content_type="application/json", data=json.dumps(body))
        assert LoadTestMixin().check_valid_body(request) == expect

    @pytest.mark.parametrize("body, expect", [
        ({"sql_query": 1}, "SQL query is required"),
        ({"sql_quer": "Select * from db"}, "SQL query is required"),
        ({"sql_query": "", "sql_params": ["pipka"]}, "SQL query is required"),
        ({"sql_params": ["pipka"]}, "SQL query is required"),
    ])
    def test_sql_query_required(self, body, expect):
        request = AsyncRequestFactory().post("/", content_type="application/json", data=json.dumps(body))
        with pytest.raises(RuntimeError, match=expect):
            LoadTestMixin().check_valid_body(request)

    def test_invalid_request_body(self):
        body = "sql_query"
        request = AsyncRequestFactory().post("/", content_type="application/json", data=json.dumps(body))
        with pytest.raises(RuntimeError, match="Request body must be"):
            LoadTestMixin().check_valid_body(request)


    @pytest.mark.parametrize("body, expect", [
        ({"sql_query": "SELECT `hello`", "sql_params": "asd"}, "Params must be"),
        ({"sql_query": "SELECT `hello`", "sql_params": None}, "Params must be"),
    ])
    def test_invalid_params(self, body, expect):
        request = AsyncRequestFactory().post("/", content_type="application/json", data=json.dumps(body))
        with pytest.raises(RuntimeError, match=expect):
            LoadTestMixin().check_valid_body(request)


    @pytest.mark.parametrize("body", [
        {"sql_quer": "Select * from db", "sql_params": ["pipka"]},
        {"sql_query": "", "sql_params": ["pipka"]},
        {"sql_params": ["pipka"]},
    ], ids=["Invalid query_param", "Empty sql_query", "No sql_query"])
    def test_no_sql_query(self, body):
        request = AsyncRequestFactory().post("/", content_type="application/json", data=json.dumps(body))
        with pytest.raises(RuntimeError, match="SQL query is required"):
            LoadTestMixin().check_valid_body(request)

    @pytest.mark.django_db
    @pytest.mark.parametrize("sql, params, col, rows", [
        ("SELECT id FROM client", [], ["id"], []),
        ("SELECT %s::integer AS first_value, %s::integer AS second_value, %s::text AS third_value",
         ["10", "20", "smth"],
         ["first_value", "second_value", "third_value"],
         [[10, 20, 'smth']]
         ),
    ], ids=["Any request", "Many params"])
    def test_success_execute_sql(self, sql, params, col, rows, result_execute_sql_factory):
        assert LoadTestMixin.execute_sql(sql, params) == result_execute_sql_factory(col, rows)
