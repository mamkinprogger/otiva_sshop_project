import redis from 'k6/x/redis';

const REDIS_URL="redis://:otiva_shop_redispass2@redis:6379";
const REDIS_CLIENT = REDIS_URL + "/0"
const REDIS_BROKER = REDIS_URL + "/1";

export const redisClient = new redis.Client(REDIS_CLIENT);
export const redisBroker = new redis.Client(REDIS_BROKER)
