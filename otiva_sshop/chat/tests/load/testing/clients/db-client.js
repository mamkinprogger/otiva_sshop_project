import http from "k6/http";
import {BASE_URL} from "../config/environments.js";

export class DBClient {
    constructor(token) {
        this.token = token;
        if (!this.token) {
            throw new Error("DB_ACCESS_TOKEN is not defined");
        }
    }

    dbRead(payload) {
        return http.post(
            `${BASE_URL}/loadtest/`,
            JSON.stringify(payload),
            {
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `${this.token}`,
                },
                tags: {
                    endpoint: "loadtest",
                },
            }
        );
    }
}

const dbAccessToken = open("/run/secrets/db_access_token").trim();
export const dbClient = new DBClient(dbAccessToken)
