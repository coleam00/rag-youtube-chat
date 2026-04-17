"""Initial migration: create all tables in Postgres.

Revision ID: 0001
Revises:
Create Date: 2026-04-17

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ---- Users table (from postgres.py) ----------------------------------
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email CITEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_login_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS users_email_idx ON users (email)")

    # Drop placeholder counter columns if they exist (leftover from #51)
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS daily_message_count")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS rate_window_start")

    # ---- User messages audit table (from postgres.py) ----------------------
    op.execute(
        """
        CREATE TABLE user_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS user_messages_user_id_created_at_idx
        ON user_messages (user_id, created_at DESC)
        """
    )

    # ---- Signup attempts table (from postgres.py) --------------------------
    op.execute(
        """
        CREATE TABLE signup_attempts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ip INET NOT NULL,
            email_attempted CITEXT,
            outcome TEXT NOT NULL CHECK (outcome IN (
                'accepted','ip_limited','global_limited','duplicate','invalid'
            )),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS signup_attempts_ip_created_at_idx
        ON signup_attempts (ip, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS signup_attempts_created_at_idx
        ON signup_attempts (created_at DESC)
        """
    )

    # ---- Videos table (from schema.py) ------------------------------------
    op.execute(
        """
        CREATE TABLE videos (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            url TEXT NOT NULL,
            transcript TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ---- Chunks table (from schema.py) ------------------------------------
    # embeddings stored as REAL[] (native Postgres array) not JSON text
    op.execute(
        """
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding REAL[] NOT NULL,
            chunk_index INTEGER NOT NULL
        )
        """
    )

    # ---- Conversations table (from schema.py) -----------------------------
    op.execute(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT 'New Conversation',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS conversations_user_id_idx
        ON conversations (user_id)
        """
    )

    # ---- Messages table (from schema.py) ----------------------------------
    op.execute(
        """
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP TABLE IF EXISTS videos")
    op.execute("DROP TABLE IF EXISTS signup_attempts")
    op.execute("DROP TABLE IF EXISTS user_messages")
    op.execute("DROP TABLE IF EXISTS users")
    # Extensions are intentionally kept — they persist across migrations
