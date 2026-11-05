
function randomString(length, alphabet) {
    let result = '';

    for (let i = 0; i < length; i++) {
        result += alphabet[
            Math.floor(Math.random() * alphabet.length)
        ];
    }

    return result;
}

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';

const ALPHANUMERIC =
    LETTERS + '0123456789-_';

export function createMessage({
    withCall = false,
    itemId = true,
    text = true,
    read = false,
    managerIds = [],
} = {}) {
    const timestamp = Math.floor(Date.now() / 1000);

    const managerIdsSet = new Set(managerIds);

    let authorId;
    do {
        authorId = Math.floor(
            Math.random() * 1_000_000_000_000
        ) + 1;
    } while (managerIdsSet.has(authorId));

    const content = {
        call: withCall
            ? {
                status: 'missed',
                target_user_id: 94235311,
            }
            : null,
    };

    if (text) {
        content.text = 'Something text';
    }

    return {
        id: "abc",
        payload: {
            type: 'message',
            value: {
                author_id: authorId,
                chat_id: randomString(30, ALPHANUMERIC),
                created: timestamp,
                item_id: itemId
                    ? Math.floor(Math.random() * 1_000_000_000_000) + 1
                    : null,
                content,
                read: read ? timestamp + 1 : null,
                id: randomString(30, LETTERS),
            }
        }
    };
}
