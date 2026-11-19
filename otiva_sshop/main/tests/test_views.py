import json

import pytest

from main.views import LoadTestView


@pytest.fixture
def logger_off(mocker):
    turn_off = mocker.patch("main.views.logger")
    return turn_off


class TestLoadTestView:
    @staticmethod
    def _get_url():
        return "http://localhost:8000/loadtest/"

    @pytest.mark.django_db
    async def test_successful_query(
            self,
            async_client,
            mocker,
            result_execute_sql_factory,
            logger_off,
    ):
        headers = {"Authorization": "token"}
        body = {
            "sql_params": ["helloeveryone)"],
            "sql_query": """
                         SELECT EXISTS (SELECT 1
                                        FROM client_chat_avito AS chat
                                                 INNER JOIN client AS client
                                                            ON client.client_id = chat.client_member_id
                                        WHERE chat.chat_id = %s) AS client_exists;
                         """,
        }

        mocker.patch.object(
            LoadTestView,
            "check_auth",
            return_value=True,
        )

        response = await async_client.post(
            self._get_url(),
            headers=headers,
            data=json.dumps(body),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json() == result_execute_sql_factory(["client_exists"], [[False]])

    async def test_incorrect_token(self, async_client):
        headers = {"Authorization": "token"}
        body = {"sql_params": ")"}

        response = await async_client.post(
            self._get_url(),
            headers=headers,
            data=json.dumps(body),
            content_type="application/json"
        )
        response_data = response.json()

        assert response.status_code == 401
        assert response_data == {"error": "Unauthorized"}

    async def test_invalid_request_body(self, async_client, mocker):
        mocker.patch.object(LoadTestView, "check_auth", return_value=True)
        headers = {"Authorization": "token"}
        body = {"sql_params": ")"}

        response = await async_client.post(
            self._get_url(),
            headers=headers,
            data=json.dumps(body),
            content_type="application/json"
        )
        response_data = response.json()

        assert response.status_code == 400
        assert response_data == {"error": "SQL query is required"}

    @pytest.mark.django_db
    async def test_incorrect_sql(self, async_client, mocker, logger_off):
        mocker.patch.object(LoadTestView, "check_auth", return_value=True)
        headers = {"Authorization": "token"}
        body = {"sql_query": "SELECT 'HI'", "sql_params": [")"]}

        response = await async_client.post(
            self._get_url(),
            headers=headers,
            data=json.dumps(body),
            content_type="application/json"
        )
        response_data = response.json()

        assert response.status_code == 400
        assert "SQL execution failed" in response_data.get("error")
        logger_off.warning.assert_called_once()


