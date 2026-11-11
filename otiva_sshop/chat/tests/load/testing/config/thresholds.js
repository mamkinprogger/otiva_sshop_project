export const thresholds = {
    common: {
        http_req_failed: ["rate<0.01"],
        checks: [
            "rate>0.99",
        ],
        "http_req_duration{endpoint:webhook}": ["p(95)<2000"]
    },

    smoke: {
        webhook_resp: {},
    },

    average: {
        webhook_resp: {},
    },
};