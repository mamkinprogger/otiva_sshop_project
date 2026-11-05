import http from 'k6/http';
import { check, sleep } from 'k6';

import redis from 'k6/x/redis';


import { createMessage } from '../lib/payloads.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const ENDPOINT = '/webhook/';
const REDIS_URL="redis://:otiva_shop_redispass2@redis:6379";

const redisClient = new redis.Client(REDIS_URL);

if (!ENDPOINT) {
    throw new Error('ENDPOINT environment variable is required');
}

export const options = {
    vus: 1,
    duration: '30s',

    thresholds: {
        http_req_failed: ['rate<0.01'],
        http_req_duration: ['p(95)<1000'],
    },
};

export async function setup() {
    const managerIds = await redisClient.hkeys('managers');

    if (!managerIds || managerIds.length === 0) {
        throw new Error('No managers found in Redis hash "managers"');
    }

    const parsedManagerIds = managerIds.map(Number);

    if (parsedManagerIds.some(id => !Number.isSafeInteger(id))) {
        throw new Error('Redis contains invalid manager IDs');
    }

    console.log(`Loaded managers from Redis: ${parsedManagerIds}`);

    return {
        managerIds: parsedManagerIds,
    };
}

export default function () {
    const payload = createMessage();

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
        tags: {
            endpoint: 'webhook',
        },
    };

    const response = http.post(
        `${BASE_URL}${ENDPOINT}`,
        JSON.stringify(payload),
        params
    );

    check(response, {
        'status is 2xx': (r) => r.status >= 200 && r.status < 300,
    });

    sleep(1);
}
