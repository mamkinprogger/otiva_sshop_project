import { sleep } from "k6";

export function waitFor(
    condition,
    {
        timeout = 15,
        interval = 0.5,
        stopStatuses = [400, 401],
        attemptsMetric = null,
    } = {}
) {
    const attempts = Math.ceil(timeout / interval);

    for (let i = 0; i < attempts; i++) {
        let result = condition()

        if (result && stopStatuses.includes(result.status)) {
            if (attemptsMetric) attemptsMetric.add(i + 1);
            return result;
        }

        if (result) {
            if (attemptsMetric) attemptsMetric.add(i + 1);
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
        attemptsMetric = null,
    } = {}
) {
    const attempts = Math.ceil(timeout / interval);

    for (let i = 0; i < attempts; i++) {
        let result = await condition()
        if (result) {
            if (attemptsMetric) attemptsMetric.add(i + 1);
            return result;
        }
        sleep(interval);
    }
    return false;
}
