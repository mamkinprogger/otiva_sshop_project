import { sleep } from "k6";

export function waitFor(
    condition,
    {
        timeout = 15,
        interval = 0.5,
    } = {}
) {
    const attempts = Math.ceil(timeout / interval);

    for (let i = 0; i < attempts; i++) {
        let res = condition()
        if (res) {
            return res;
        }
        sleep(interval);
    }
    return false;
}


export async function awaitFor(
    condition,
    {
        timeout = 15,
        interval = 0.5,
    } = {}
) {
    const attempts = Math.ceil(timeout / interval);

    for (let i = 0; i < attempts; i++) {
        let res = await condition()
        if (res) {
            return res;
        }

        sleep(interval);
    }

    return false;
}
