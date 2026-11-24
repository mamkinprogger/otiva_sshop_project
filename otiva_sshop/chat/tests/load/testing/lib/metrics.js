import { Trend } from 'k6/metrics';


export const dbCheckResponse = new Trend('dbCheckResponse');
export const redisCheckResponse = new Trend('redisCheckResponse');
export const mailpitCheckResponse = new Trend('mailpitCheckResponse');

export const messagesPending = new Trend('messages_pending');
