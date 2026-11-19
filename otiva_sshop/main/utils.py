import hashlib
import hmac
import json

from django.core.handlers.asgi import ASGIRequest
from django.db import transaction, connection

from app.settings import LOADTEST_HASH, MAX_ROWS


class LoadTestMixin:
    @staticmethod
    def check_auth(token: str | None) -> bool:
        if not token:
            return False
        loadtest_token = hashlib.sha256(token.encode()).digest()
        return hmac.compare_digest(loadtest_token, LOADTEST_HASH)

    @staticmethod
    def check_valid_body(request: ASGIRequest) -> tuple:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError("Invalid request body")

        if not isinstance(body, dict):
            raise RuntimeError("Request body must be a JSON object")

        sql_query = body.get("sql_query", "")
        sql_params = body.get("sql_params", [])

        if not isinstance(sql_query, str) or not sql_query.strip():
            raise RuntimeError("SQL query is required")
        elif not isinstance(sql_params, (list, dict)):
            raise RuntimeError("Params must be a list or dict")

        return sql_query, sql_params

    @staticmethod
    def execute_sql(sql: str, params: list[str | None]):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                cursor.execute("SET LOCAL lock_timeout = '1s'")

                cursor.execute(sql, params)

                if cursor.description is None:
                    return {
                        "columns": [],
                        "data": [],
                        "count": 0,
                        "truncated": False,
                    }

                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchmany(MAX_ROWS + 1)
                return {
                    "columns": columns,
                    "data": [
                        dict(zip(columns, row))
                        for row in rows[:MAX_ROWS]
                    ],
                    "count": min(len(rows), MAX_ROWS),
                    "truncated": len(rows) > MAX_ROWS,
                }