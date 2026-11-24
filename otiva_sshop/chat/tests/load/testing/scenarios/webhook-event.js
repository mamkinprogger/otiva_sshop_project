import {check} from "k6";

import {redisBroker, redisClient} from "../lib/redis-client.js";

import {createMessage, randomString} from "../lib/data-generator.js";
import {WebhookClient} from "../clients/webhook-client.js";
import {awaitFor, waitFor} from "../lib/wait-for.js";
import {getMailsCount} from "../lib/mailpit-client.js";
import { clientMsgsCountQuery} from "../lib/pg_queries.js";
import {dbClient} from "../clients/db-client.js";
import {
    dbCheckResponse,
    mailpitCheckResponse,
    messagesPending,
    redisCheckResponse
} from "../lib/metrics.js";


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
        'response lag set': (value) =>
            Number(value?.split(':').at(-1)) === payload.payload.value.created,
    });
    check(response, {"webhook returns 2xx": (r) => r.status >= 200 && r.status < 300});
    return payload;
}

export async function totalCheckVU(managerId, chatId, totalMsgs){
    // check all emails sent
    const EmailsSent = waitFor(
        () => {
            const res = Number(getMailsCount(chatId));
            if (!res) return false;
            return res >= 2 && res < 6 ? res : false;
            },
        {
        timeout: 15,
        attemptsMetric: mailpitCheckResponse
        }
    );
    check(EmailsSent, {"all emails sent": (value) => value >= 2 && value < 6});


    //check manager answered on all messages
    const managerAnswered = await awaitFor(
        async () => redisClient.get(chatId),
        {timeout: 5, attemptsMetric: redisCheckResponse}
    )
    check(managerAnswered, {
        "answer all questions": (value) => Number(value.split(':')[1]) === 0
    });


    // check written all messages
    const msgsCount = waitFor(
    () => {
        const response = dbClient.dbRead(
            clientMsgsCountQuery(chatId)
        );
        if (response.status !== 200) return false;
        const count = JSON.parse(response.body).data?.[0]?.emails_count;
        return count === totalMsgs ? response : false;
    },
    {
        timeout: 15,
        attemptsMetric: dbCheckResponse,
    }
    );
    check(msgsCount, {
        'msgs client written': (r) => {
            if (r.status !== 200) return false;
            return JSON.parse(r.body).data?.[0]?.emails_count === totalMsgs;
            },
    });

    const pendingCount = await redisBroker.llen(managerId);
    messagesPending.add(pendingCount)
}
