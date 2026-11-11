import http from "k6/http";

const MAILPIT_URL = "http://mailpit:8025";

export function mailExists(chatId) {
    const query = `subject:"${chatId}"`;

    const response = http.get(
        `${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(query)}`
    );

    if (response.status !== 200) {
        return false;
    }

    const body = response.json();

    return body.messages_count === 5;
}
