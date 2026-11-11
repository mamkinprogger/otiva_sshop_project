import {sleep} from "k6";

import { workloads } from "../config/workloads.js";
import { thresholds } from "../config/thresholds.js";

import {managerSendMessage, newClientSendMessage, oldClientSendMessage} from "../scenarios/views/webhook-event.js";
import {loadManagerIds} from "../lib/managres.js";
import {redisClient} from "../lib/redis-client.js";


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
    const redisVal = await redisClient.get(chatId);
    const managerId = Number(redisVal.split(':')[0]);

    await managerSendMessage(managerId, chatId);
    sleep(1);

    for (let i = 0; i < 4; i++) {
        await oldClientSendMessage(payload);
        sleep(1);

        await managerSendMessage(managerId, chatId);
        sleep(1)
    }
}
