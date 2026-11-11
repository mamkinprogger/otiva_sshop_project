import { check } from "k6";

import {redisClient} from "../../lib/redis-client.js";

import {createMessage, randomString} from "../../lib/data-generator.js";
import { WebhookClient } from "../../clients/webhook-client.js";

export async function newClientSendMessage(managerIds) {
    const payload = createMessage({
        managerIds,
    });
    const chatId = payload.payload.value.chat_id;

    const client = new WebhookClient();
    const response = client.sendMessage(payload);

    const chatAdded = await redisClient.exists(chatId);
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
    // console.log(`Manger sended message chat_id: ${chatId}`);

    const chatResponseUpdated = await redisClient.get(chatId);
    // console.log(`${chatResponseUpdated} Manger answered the message`);
    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});
    check(chatResponseUpdated, {
        'response lag written': (value) => value?.split(':').at(-1) === '0',
    });
    return payload;
}


export async function oldClientSendMessage(payload) {
    const client = new WebhookClient();
    payload.payload.value.created = Math.floor(Date.now() / 1000);
    payload.payload.value.content.text = randomString(30);

    const response = client.sendMessage(payload);
    const redisValue = await redisClient.get(payload.payload.value.chat_id);
    // console.log(`${redisValue} oldClient send message chat_id: ${payload.payload.value.chat_id}`);

    check(redisValue, {
        'response lag set': (value) => value?.split(':').at(-1) == payload.payload.value.created,
    });
    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});
    return payload;
}
