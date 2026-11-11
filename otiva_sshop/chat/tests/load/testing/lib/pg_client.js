import sql from "k6/x/sql";
import driver from "k6/x/sql/driver/postgres";

const db = sql.open(driver, __ENV.POSTGRES_DSN);

export function clientExists(chatId) {
    const rows = db.query(
        `
        SELECT EXISTS (
            SELECT 1
            FROM client_chat_avito AS chat
            INNER JOIN client AS client
                ON client.client_id = chat.client_member_id
            WHERE chat.chat_id = $1
        ) AS client_exists;
        `,
        chatId
    );

    return rows[0].client_exists;
}

export function closeDatabase() {
    db.close();
}
