import pytest

from app.settings import MAX_ROWS


@pytest.fixture
def result_execute_sql_factory():
    def create_sql_result(col: list[str], rows: list[str|int]) -> dict:
        result = {
            "columns": col,
            "data": [
                dict(zip(col, row))
                for row in rows[:MAX_ROWS]
            ],
            "count": min(len(rows), MAX_ROWS),
            "truncated": len(rows) > MAX_ROWS,
        }
        return result
    return create_sql_result