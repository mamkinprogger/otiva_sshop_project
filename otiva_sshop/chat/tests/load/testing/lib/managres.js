import {redisClient} from "./redis-client.js";

export async function loadManagerIds() {
    const managerIds = await redisClient.hkeys("managers");
    if (!managerIds || managerIds.length === 0) {
        throw new Error('No managers found in Redis hash "managers"');
    }

    const parsedManagerIds = managerIds.map(Number);
    if (parsedManagerIds.some(id => !Number.isSafeInteger(id) || id <= 0)) {
        throw new Error("Redis contains invalid manager IDs");
    }

    console.log(`Loaded managers from Redis: ${parsedManagerIds}`);
    return parsedManagerIds;
}
