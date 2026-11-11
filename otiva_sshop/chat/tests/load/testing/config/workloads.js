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
                { duration: "1m", target: 150 },
                { duration: "2m", target: 150 }, //220 верхний порог, за ним уже postgres не выдерживает столько подключений -> делаем пул подключений
                { duration: "1m", target: 0 },
            ],
            gracefulRampDown: "10s"
        },
        notif_send: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
                { duration: "1m", target: 18 },
                { duration: "2m", target: 36 }, //50 верхний порог, за ним уже postgres не выдерживает столько подключений -> нужно устанавливать пулл подключений
                { duration: "1m", target: 0 },
            ],
            gracefulRampDown: "15s"
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