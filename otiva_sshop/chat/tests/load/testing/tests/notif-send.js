import {check, sleep} from "k6";

import {workloads} from "../config/workloads.js";
import {thresholds} from "../config/thresholds.js";

import {
    managerSendMessage,
    newClientSendMessage,
    oldClientSendMessage,
    totalCheckVU
} from "../scenarios/webhook-event.js";
import {loadManagerIds} from "../lib/managres.js";
import {redisClient} from "../lib/redis-client.js";
import {clientExistsQuery} from "../lib/pg_queries.js";
import {awaitFor, waitFor} from "../lib/wait-for.js";
import {dbClient} from "../clients/db-client.js";
import {dbCheckResponse} from "../lib/metrics.js";


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
    const chatId = payload.payload.value.chat_id;
    sleep(1);


    const redisVal = await awaitFor(
        async () => redisClient.get(chatId),
        {timeout: 5}
    )
    const managerId = Number(redisVal.split(':')[0]);

    await managerSendMessage(managerId, chatId);
    sleep(1);


    const clientCreated = waitFor(
        () => {
            const response = dbClient.dbRead(clientExistsQuery(chatId));
            const exist = JSON.parse(response.body).data?.[0]?.client_exists;
            return exist ? response : false;
        },
        {
            timeout: 15,
            attemptsMetric: dbCheckResponse
        }
    );
    check(clientCreated, {
        'DB returned one row': (r) => {
            if (r.status !== 200) return false;
            return JSON.parse(r.body).count === 1;
            },
        'client exists in PostgreSQL': (r) => {
            if (r.status !== 200) return false;
            return JSON.parse(r.body).data?.[0]?.client_exists === true;
            },
    });


    for (let i = 0; i < 4; i++) {
        await redisClient
        await oldClientSendMessage(payload);
        sleep(1);

        await managerSendMessage(managerId, chatId);
        sleep(1)
    }
    await totalCheckVU(managerId, chatId, 5)

}
