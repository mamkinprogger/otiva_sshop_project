import {sleep} from "k6";

import { workloads } from "../config/workloads.js";
import { thresholds } from "../config/thresholds.js";

import {newClientSendMessage} from "../scenarios/views/webhook-event.js";
import {loadManagerIds} from "../lib/managres.js";


const test_type = __ENV.TEST_TYPE || "smoke";
if (!workloads[test_type]) {
    throw new Error(
        `Unknown TEST_PROFILE: "${test_type}". Available test_types: ${Object.keys(workloads).join(", ")}`
    );
}

export const options = {
    scenarios: {
        main: {
            ...workloads[test_type]["webhook_resp"],
        },
    },
    thresholds: {
        ...thresholds.common,
        ...thresholds[test_type]["webhook_resp"],
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

export default async function (data) {  // порог до ошибок 220 vus илм 90 avg http/s. Затем pg не выдерживает
    await newClientSendMessage(data.managerIds);
    sleep(1);
}

// export default async function (data) {
//     const payload = await newClientSendMessage(data.managerIds);
//     for (let i = 0; i < 10; i++) {
//         await oldClientSendMessage(payload); // не обновляет тварь запись в redis
//         sleep(1)
//     }
// }
