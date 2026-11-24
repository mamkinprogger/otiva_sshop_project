

export function clientExistsQuery(chatId) {
    return {
        sql_query: `
            SELECT EXISTS (
                SELECT 1
                FROM client_chat_avito AS chat
                INNER JOIN client AS client
                    ON client.client_id = chat.client_member_id
                WHERE chat.chat_id = %s
            ) AS client_exists;
        `,
        sql_params: [chatId],
    };
}

export function clientMsgsCountQuery(chatId) {
    return {
        sql_query: `
            SELECT client.emails_count
            FROM client_chat_avito AS chat
            INNER JOIN client AS client
                ON client.client_id = chat.client_member_id
            WHERE chat.chat_id = %s;
        `,
        sql_params: [chatId],
    };
}