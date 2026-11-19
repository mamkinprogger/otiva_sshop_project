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
            stages: [
                { duration: "1m", target: 26 },
                { duration: "2m", target: 26 }, //36 верхний порог, за ним уже postgres не выдерживает столько подключений -> нужно устанавливать пулл подключений
                { duration: "1m", target: 0 },
            ],
            gracefulRampDown: "30s"
        },
    },
};