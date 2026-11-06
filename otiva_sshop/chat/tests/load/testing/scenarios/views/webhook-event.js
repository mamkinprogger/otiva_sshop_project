import { check } from "k6";

import { createMessage } from "../../lib/data-generator.js";
import { WebhookClient } from "../../clients/webhook-client.js";

export function sendMessage(managerIds) {
    const payload = createMessage({
        managerIds,
    });

    const client = new WebhookClient();
    const response = client.sendMessage(payload);

    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});

    return response;
}
