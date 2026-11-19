import { sleep } from "k6";

export function waitFor(
    condition,
    {
        timeout = 15,
        interval = 0.5,
        stopStatuses = [400, 401],
    } = {}
) {
    const attempts = Math.ceil(timeout / interval);

    for (let i = 0; i < attempts; i++) {
        let result = condition()

        if (result && stopStatuses.includes(result.status)) {
            return result;
        }

        if (result) {
            return result;
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
        let result = await condition()
        if (result) {
            return result;
        }
        sleep(interval);
    }

    return false;
}
