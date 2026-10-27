"""Memory service encapsulating GDPR export, session retention, and right-to-be-forgotten deletion."""

from typing import Any

from loguru import logger

from amberclaw.memory.session_db import SessionDB


class MemoryService:
    """Service providing privacy-preserving session and interaction memory management."""

    def __init__(self, session_db: SessionDB | None = None) -> None:
        self.session_db = session_db or SessionDB()

    def export_data(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Export stored interaction records with SHA-256 integrity verification (GDPR Art. 15/20)."""
        logger.info(
            "Exporting memory data for user={}, session={}, org={}",
            user_id,
            session_id,
            org_id,
        )
        return self.session_db.export_user_data(
            user_id=user_id,
            session_id=session_id,
            org_id=org_id,
        )

    def delete_session(self, session_id: str) -> int:
        """Permanently delete all stored interaction turns for a specific session ID (GDPR Art. 17)."""
        deleted_count = self.session_db.delete_session(session_id)
        logger.info(
            "Deleted {} memory turns for session '{}'", deleted_count, session_id
        )
        return deleted_count

    def delete_user(self, user_id: str) -> int:
        """Permanently delete all stored interaction turns across all sessions for a specific user ID."""
        with self.session_db._lock:
            try:
                cursor = self.session_db.conn.execute(
                    "DELETE FROM session_turns WHERE user_id = ?;",
                    (user_id,),
                )
                deleted_count = cursor.rowcount
                self.session_db.conn.execute(
                    "DELETE FROM session_turns_fts WHERE user_id = ?;",
                    (user_id,),
                )
                self.session_db.conn.commit()
                logger.info(
                    "Deleted {} memory turns for user '{}'", deleted_count, user_id
                )
                return deleted_count
            except Exception as e:
                logger.error("Failed to delete user {}: {}", user_id, e)
                self.session_db.conn.rollback()
                return 0
