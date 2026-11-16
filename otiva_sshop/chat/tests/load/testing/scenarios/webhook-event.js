import { check } from "k6";

import {redisClient} from "../lib/redis-client.js";

import {createMessage, randomString} from "../lib/data-generator.js";
import { WebhookClient } from "../clients/webhook-client.js";
import {awaitFor} from "../lib/wait-for.js";


export async function newClientSendMessage(managerIds) {
    const payload = createMessage({
        managerIds,
    });
    const chatId = payload.payload.value.chat_id;

    const client = new WebhookClient();
    const response = client.sendMessage(payload);

    const chatAdded = await awaitFor(
        async () => redisClient.exists(chatId),
        {timeout: 5}
    )

    check(chatAdded, {'chat written in Redis': (value) => value === 1});
    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});

    return payload;
}


export async function managerSendMessage(managerId, chatId) {
    const payload = createMessage()
    payload.payload.value.author_id = managerId;
    payload.payload.value.chat_id = chatId;

    const manager = new WebhookClient();
    const response = manager.sendMessage(payload);

    const chatResponseUpdated = await awaitFor(
        async () => redisClient.get(chatId),
        {timeout: 5}
    )

    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});
    check(chatResponseUpdated, {
        'response lag in Redis': (value) => value?.split(':').at(-1) === '0',
    });
    return payload;
}


export async function oldClientSendMessage(payload) {
    const client = new WebhookClient();
    payload.payload.value.created = Math.floor(Date.now() / 1000);
    payload.payload.value.content.text = randomString(30);

    const response = client.sendMessage(payload);
    const redisValue = await awaitFor(
        async () => redisClient.get(payload.payload.value.chat_id),
        {timeout: 5}
    )

    check(redisValue, {
        'response lag set': (value) => value?.split(':').at(-1) == payload.payload.value.created,
    });
    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});
    return payload;
}
