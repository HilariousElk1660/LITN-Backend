from fastapi import APIRouter, Depends

from core.database import get_connection
from core.security import get_current_user

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/me")
async def get_my_library(current_user: dict = Depends(get_current_user)):
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                rb.reader_book_id,
                rb.book_id,
                b.book_name,
                b.author_name,
                b.book_cover_url,
                rb.current_page,
                rb.total_pages,
                rb.current_chapter_index,
                b.chapters AS total_chapters,
                rb.percentage_completed,
                rb.progress,
                rb.last_opened,
                rp.page_stopped_at,
                rp.last_opened_on
            FROM readers_books rb
            JOIN books b ON b.book_id = rb.book_id
            LEFT JOIN reading_progress rp
                ON rp.book_id = rb.book_id AND rp.reader_id = rb.user_id
            WHERE rb.user_id = $1
            ORDER BY rb.last_opened DESC NULLS LAST
            """,
            current_user["user_id"],
        )

    return [dict(r) for r in rows]