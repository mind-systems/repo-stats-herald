import asyncpg


def _encode_vector(value: list[float]) -> str:
    return "[" + ",".join(str(component) for component in value) + "]"


def _decode_vector(text: str) -> list[float]:
    return [float(component) for component in text.strip("[]").split(",")]


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "vector",
        schema="public",
        encoder=_encode_vector,
        decoder=_decode_vector,
        format="text",
    )


async def create_pool(dsn: str) -> asyncpg.Pool:
    """Open an asyncpg connection pool against `dsn`.

    Every connection registers a text codec for pgvector's `vector` type so
    embeddings marshal directly as `list[float]` on both ends — callers never
    see pgvector's wire format.
    """
    return await asyncpg.create_pool(dsn, init=_init_connection)
