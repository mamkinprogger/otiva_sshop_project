import {sleep} from "k6";

import { workloads } from "../config/workloads.js";
import { thresholds } from "../config/thresholds.js";

import {sendMessage} from "../scenarios/views/webhook-event.js";
import {loadManagerIds} from "../lib/managres.js";


const test_type = __ENV.TEST_TYPE || "smoke";
if (!workloads[test_type]) {
    throw new Error(
        `Unknown TEST_PROFILE: "${test_type}". Available test_types: ${Object.keys(workloads).join(", ")}`
    );
}

export const options = {
    ...workloads[test_type],
    thresholds: {
        ...thresholds.common,
        ...thresholds[test_type],
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


export default function (data) {
    sendMessage(data.managerIds);
    sleep(1);
}
