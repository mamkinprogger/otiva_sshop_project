import {check, sleep} from "k6";

import { workloads } from "../config/workloads.js";
import { thresholds } from "../config/thresholds.js";

import {managerSendMessage, newClientSendMessage, oldClientSendMessage} from "../scenarios/webhook-event.js";
import {loadManagerIds} from "../lib/managres.js";
import {redisClient} from "../lib/redis-client.js";
import {clientExists, closeDatabase} from "../lib/pg_client.js";
import {awaitFor, waitFor} from "../lib/wait-for.js";
import {mailExists} from "../lib/mailpit-client.js";


const test_type = __ENV.TEST_TYPE || "smoke";
if (!workloads[test_type]) {
    throw new Error(
        `Unknown TEST_PROFILE: "${test_type}". Available test_types: ${Object.keys(workloads).join(", ")}`
    );
}

export const options = {
    scenarios: {
        main: {
            ...workloads[test_type]["notif_send"],
        },
    },
    thresholds: {
        ...thresholds.common,
        ...thresholds[test_type]["notif_send"],
    },
    tags: {
        test_type: test_type,
    },
};


export async function setup() {
    return {
        managerIds: await loadManagerIds(),
    };
}


export default async function (data) {
    const payload = await newClientSendMessage(data.managerIds);
    sleep(1);

    const chatId = payload.payload.value.chat_id;
    const redisVal = await awaitFor(
        async () => redisClient.get(chatId),
        {timeout: 5}
    )
    const managerId = Number(redisVal.split(':')[0]);

    await managerSendMessage(managerId, chatId);
    sleep(1);

    const clientCreated = waitFor(
        () => clientExists(chatId),
        { timeout: 15 }
    );
    check(clientCreated, {"client created in PostgreSQL": (value) => value === true});

    for (let i = 0; i < 4; i++) {
        await oldClientSendMessage(payload);
        sleep(1);

        await managerSendMessage(managerId, chatId);
        sleep(1)
    }

    const allEmailsSent = waitFor(
        () => mailExists(chatId),
        { timeout: 15 }
    );
    check(allEmailsSent, {"all emails sent": (value) => value === true});
}


export function teardown(data) {
    closeDatabase();
}
