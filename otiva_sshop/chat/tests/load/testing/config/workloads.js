export const workloads = {
    smoke: {
        webhook_resp: {
            executor: "constant-vus",
            vus: 1,
            duration: "30s",
        },
        notif_send: {
            executor: "constant-vus",
            vus: 1,
            duration: "30s",
        },
    },

    average: {
        webhook_resp: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
                { duration: "1m", target: 500 },
                { duration: "2m", target: 500 }, //700 верхний порог, за ним уже p(95) > 2s
                { duration: "1m", target: 0 },
            ],
            gracefulRampDown: "15s"
        },
        notif_send: {
            executor: "ramping-vus",
            startVUs: 0,
            // 90 для 2х менеджеров
            // нижние stages рассчитаны на 7 менеджеров
            stages: [
                { duration: "1m", target: 200 },
                { duration: "2m", target: 200 },
                { duration: "1m", target: 0 },
            ],
            gracefulRampDown: "30s"
        },
    },
};