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

    average: { // можно добавить тут типо avg webhook-resp, avg celery-sending
        webhook_resp: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
                { duration: "1m", target: 150 },
                { duration: "2m", target: 150 }, //220 верхний порог, за ним уже postgres не выдерживает столько подключений
                { duration: "1m", target: 0 },
            ],
            gracefulRampDown: "10s"
        },
    },

    stress: {
        stages: [
            { duration: "2m", target: 50 },
            { duration: "3m", target: 100 },
            { duration: "3m", target: 200 },
            { duration: "2m", target: 0 },
        ],
    },
};