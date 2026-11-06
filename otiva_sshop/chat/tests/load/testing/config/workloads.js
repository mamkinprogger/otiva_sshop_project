export const workloads = {
    smoke: {
        executor: "shared-iterations",
        vus: 1,
        duration: "30s",
    },

    average: {
        executor: "ramping-vus",
        startVUs: 0,
        stages: [
            { duration: "1m", target: 20 },
            { duration: "2m", target: 20 },
            { duration: "1m", target: 0 },
        ],
        gracefulRampDown: "10s"
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