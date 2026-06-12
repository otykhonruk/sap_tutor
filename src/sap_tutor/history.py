import json
import sqlite3
from pathlib import Path


class MessageHistory:
    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            self.db_path = self.get_default_db_path()
        else:
            self.db_path = Path(db_path)

        # Ensure the parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to SQLite. check_same_thread=False allows sharing this connection
        # if needed, but since it is run in a single-threaded loop, it is safe.
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    @staticmethod
    def get_default_db_path() -> Path:
        # Standard data directory for docker container
        docker_data_dir = Path("/app/_data")
        if Path("/app").is_dir():
            docker_data_dir.mkdir(parents=True, exist_ok=True)
            return docker_data_dir / "signal_bot_history.db"

        # Fallback to current working directory _data folder
        local_dir = Path.cwd() / "_data"
        local_dir.mkdir(parents=True, exist_ok=True)
        return local_dir / "signal_bot_history.db"

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_key TEXT UNIQUE NOT NULL,
                    source TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    body TEXT NOT NULL,
                    group_id TEXT,
                    is_faq BOOLEAN NOT NULL DEFAULT 0,
                    query TEXT,
                    reply TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_key ON message_history(message_key)
            """)

    def is_seen(self, message_key: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM message_history WHERE message_key = ?", (message_key,))
        return cursor.fetchone() is not None

    def add_message(
        self,
        message_key: str,
        source: str,
        timestamp: int,
        body: str,
        group_id: str | None = None,
        is_faq: bool = False,
        query: str | None = None,
        reply: str | None = None,
    ):
        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO message_history (message_key, source, timestamp, body, group_id, is_faq, query, reply)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (message_key, source, timestamp, body, group_id, int(is_faq), query, reply),
                )
        except sqlite3.IntegrityError:
            # Already exists, do nothing
            pass

    def update_reply(self, message_key: str, reply: str):
        with self.conn:
            self.conn.execute(
                "UPDATE message_history SET reply = ? WHERE message_key = ?",
                (reply, message_key),
            )

    def migrate_from_json(self, json_path: Path):
        if not json_path.exists():
            return

        try:
            seen_keys = json.loads(json_path.read_text(encoding="utf-8"))
            migrated_count = 0
            for key in seen_keys:
                if self.is_seen(key):
                    continue

                # Parse: source:timestamp:body
                parts = key.split(":", 2)
                if len(parts) == 3:
                    source, timestamp_str, body = parts
                    try:
                        timestamp = int(timestamp_str)
                    except ValueError:
                        timestamp = 0
                else:
                    source = "unknown"
                    timestamp = 0
                    body = key

                self.add_message(
                    message_key=key,
                    source=source,
                    timestamp=timestamp,
                    body=body,
                    is_faq=False,
                )
                migrated_count += 1

            backup_path = json_path.with_suffix(".json.bak")
            json_path.rename(backup_path)
            print(f"Migrated {migrated_count} seen messages from {json_path} to SQLite database. Backed up to {backup_path}.")
        except Exception as e:
            print(f"Failed to migrate seen messages from JSON: {e}")

    def get_messages(self, group_id: str | None = None, all_messages: bool = False) -> list[sqlite3.Row]:
        cursor = self.conn.cursor()
        if all_messages:
            cursor.execute(
                "SELECT * FROM message_history ORDER BY timestamp ASC"
            )
        elif group_id is None:
            cursor.execute(
                "SELECT * FROM message_history WHERE group_id IS NULL ORDER BY timestamp ASC"
            )
        else:
            cursor.execute(
                "SELECT * FROM message_history WHERE group_id = ? ORDER BY timestamp ASC",
                (group_id,),
            )
        return cursor.fetchall()

    def get_unique_groups(self) -> list[str | None]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT group_id FROM message_history")
        return [row[0] for row in cursor.fetchall()]

    def close(self):
        self.conn.close()
