import http from "k6/http";
import { BASE_URL, ENDPOINT } from "../config/environments.js";

export class WebhookClient {
    sendMessage(payload) {
        return http.post(
            `${BASE_URL}${ENDPOINT}`,
            JSON.stringify(payload),
            {
                headers: {
                    "Content-Type": "application/json",
                },
                tags: {
                    endpoint: "webhook",
                },
            }
        );
    }
}
