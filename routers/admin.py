from decimal import Decimal
import json
from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends, params,BackgroundTasks,Depends,File,Form,UploadFile,status
from datetime import datetime, timedelta, date, timezone
from typing import Optional
import uuid
import os
import tempfile
import json

from pydantic import BaseModel
from core.database import get_connection
router = APIRouter()



@router.get("/admins")
async def get_admin(user_id: str):
    """
    Get a list of all admins and super admins. can only be accessed by admins
    """

    try:
        #logic to check if the user is a super admin
        
        async with get_connection() as conn:
            row = await conn.fetch(
                "SELECT fullname,email,role FROM users WHERE role = 'admin' OR role = 'super_admin'"
            )

        return row 
    except (Exception) as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching admins")

@router.patch("/change_role")
async def change_user_role(email: str, role: str):
    """
    Change the role of a user. can only be accessed by admins
    email of the user whose role needs to be changed
    """
    try:
        #add logic to check user

        async with get_connection() as conn:
            updated_user = await conn.fetch(
                "UPDATE users SET role = $1 WHERE email = $2 RETURNING fullname",
                role,
                email
            )
        if updated_user:
            return {"message": "User role updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
         
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while changing user role: " + str(e))
    

@router.get("/book_requests")
async def get_book_requests(admin_id:str):
    """Get a list of all book requests. can only be accessed by admins"""
    try:
        #add logic to check user
        async with get_connection() as conn:
            row = await conn.fetch(
                "SELECT * FROM book_requests WHERE admin_id = $1",
                admin_id
            )
        return row
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching book requests: " + str(e))
    

@router.patch("/update_book_request")
async def update_book_request(request_id: str, status: str):
    """
    Update the status of a book request. can only be accessed by admins
    """
    try:
        #add logic to check user
        async with get_connection() as conn:
            row = await conn.fetch(
                "UPDATE book_requests SET status = $1 WHERE request_id = $2 RETURNING *",
                status,
                request_id
            )
        print(row)
        if row:
            
            return {"message": "Book request updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Book request not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while updating book request: " + str(e))
    
#move to books 
@router.patch("/update_book")
async def update_book(book_id: str, price: float):
    """
    Update the price of a book. can only be accessed by admins
    """
    try:
        #add logic to check user
        async with get_connection() as conn:
            row = await conn.fetch(
                "UPDATE books SET subscription_price = $1 WHERE book_id = $2 RETURNING *",
                price,
                book_id
            )
        print(row)
        if row:
            return {"message": "Book updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Book not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while updating book: " + str(e))


#move to users

class Book_request(BaseModel):
    book_id: str
    admin_id: str
    reader_id: str
    reader_name: str
    reader_email: str
    book_name: str
    book_price: float


@router.post("/book_request")
async def send_book_request( book_request: Book_request):
    """
    Send a book request to book admin
    """
    try:
        #add logic to check user

        async with get_connection() as conn:
            row = await conn.execute(
                "INSERT INTO book_requests (book_id, admin_id, reader_id, reader_name, reader_email, book_name, book_price,status,) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                book_request.book_id,
                book_request.admin_id,
                book_request.reader_id,
                book_request.reader_name,
                book_request.reader_email,
                book_request.book_name,
                book_request.book_price
            )

        if row:
            return {"message": "Book request sent successfully"}
        else:
            raise HTTPException(status_code=404, detail="Book not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while sending book request: " + str(e))


