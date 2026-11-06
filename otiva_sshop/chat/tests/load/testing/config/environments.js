
const environments = {
    dev: {
        BASE_URL: "http://nginx:80",
        ENDPOINT: "/webhook/",
    },
};

const environment = __ENV.ENVIRONMENT || "dev";

if (!environments[environment]) {
    throw new Error(`Unknown environment: ${environment}`);
}

export const BASE_URL = __ENV.BASE_URL || environments[environment].BASE_URL;
export const ENDPOINT = __ENV.ENDPOINT || environments[environment].ENDPOINT;
