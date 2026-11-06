import redis from 'k6/x/redis';

const REDIS_URL="redis://:otiva_shop_redispass2@redis:6379";

export const redisClient = new redis.Client(REDIS_URL);
