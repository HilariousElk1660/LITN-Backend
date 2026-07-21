import re

from fastapi import APIRouter, HTTPException, status, Depends
from core.database import get_connection
from core.security import require_role

router = APIRouter(tags=["books"])

@router.get("/all_books")
async def all_books():
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT book_id, book_name, author_name, book_cover_url,
                   book_url, category, pages, chapters,
                   subscription_price, status, published_date, created_at
            FROM books
            ORDER BY created_at DESC
            """
        )
    return [dict(r) for r in rows]

@router.get("/readers_books/{user_id}")
async def readers_books(user_id: str):
    async with get_connection() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE user_id = $1", user_id
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        rows = await conn.fetch(
            """
            SELECT b.book_id, b.book_name, b.author_name, b.book_cover_url,
                   b.category, b.pages, b.chapters, b.status,
                   rp.status AS reading_status, rp.progress, rp.updated_at
            FROM books b
            JOIN reading_progress rp ON rp.book_id = b.book_id
            WHERE rp.user_id = $1
            ORDER BY rp.updated_at DESC
            """,
            user_id,
        )
    return [dict(r) for r in rows]

@router.delete("/delete_book/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: str,
    # current_user: dict = Depends(require_role("super-admin")),
):
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM books WHERE book_id = $1", book_id
        )
    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )
    

@router.get("/read_book/{book_id}")
async def readbook(book_id:str):
    async with get_connection() as conn:
        result = await conn.fetch(
            "SELECT * FROM book_files WHERE book_id = $1", book_id
        )
    return result[0]

@router.get("/reading_progress")
async def get_reading_progress(reader_id:str, book_id:str):
    print("here")
    async with get_connection() as conn:
        result = await conn.fetch(
            "SELECT * FROM reading_progress WHERE book_id = $1  AND reader_id = $2", 
            book_id,
            reader_id
        )
   
    if result:    
        return result[0]
    return {}

@router.post("/save_reading_progress")
async def save_reading_progress(reader_id:str, book_id:str, page_stopped_at:int):
    async with get_connection() as conn:
        result = await conn.fetch(
            """
            INSERT INTO reading_progress (page_stopped_at, book_id, reader_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (book_id, reader_id)
            DO UPDATE SET page_stopped_at = EXCLUDED.page_stopped_at
            """, 
            str(page_stopped_at),
            book_id, 
            reader_id
        )
    print(result)
    return result