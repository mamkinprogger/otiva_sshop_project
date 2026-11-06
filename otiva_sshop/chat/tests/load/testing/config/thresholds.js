export const thresholds = {
    common: {
        http_req_failed: ["rate<0.01"],
        checks: [
            "rate>0.99",
        ],
        "http_req_duration{endpoint:webhook}": ["p(95)<2000"]
    },

    smoke: {
        http_req_duration: ["p(95)<2000"],

    },

    average: {
        http_req_duration: ["p(95)<2000"],
    },
};