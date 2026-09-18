from sqlalchemy import text


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_node_usage (
    user_uuid TEXT NOT NULL,
    node_id INTEGER NOT NULL,
    last_usage INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_uuid, node_id),
    FOREIGN KEY(user_uuid) REFERENCES users(uuid) ON DELETE CASCADE,
    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
)
"""


def ensure_usage_table(db):
    db.execute(text(CREATE_TABLE_SQL))


def get_last_usage(db, user_uuid: str, node_id: int):
    row = db.execute(
        text(
            """
            SELECT last_usage
            FROM user_node_usage
            WHERE user_uuid = :user_uuid
              AND node_id = :node_id
            """
        ),
        {
            "user_uuid": user_uuid,
            "node_id": node_id,
        },
    ).first()

    if row is None:
        return None

    return int(row[0] or 0)


def set_last_usage(
    db,
    user_uuid: str,
    node_id: int,
    last_usage: int,
):
    db.execute(
        text(
            """
            INSERT INTO user_node_usage (
                user_uuid,
                node_id,
                last_usage
            )
            VALUES (
                :user_uuid,
                :node_id,
                :last_usage
            )
            ON CONFLICT(user_uuid, node_id)
            DO UPDATE SET
                last_usage = excluded.last_usage
            """
        ),
        {
            "user_uuid": user_uuid,
            "node_id": node_id,
            "last_usage": int(last_usage or 0),
        },
    )
