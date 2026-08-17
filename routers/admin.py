from decimal import Decimal
import json
from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends, params,BackgroundTasks,Depends,File,Form,UploadFile,status
from datetime import datetime, timedelta, date, timezone
from typing import Optional
import uuid
import os
import tempfile
import json
from core.security import get_current_user
# import requests
from pydantic import BaseModel
from core.database import get_connection
from core.security import require_role
from dotenv import load_dotenv
import os
router = APIRouter()



@router.get("/admins")
async def get_admin(
    current_user: dict = Depends(require_role("admin", "super-admin")),
):
    """
    Get a list of all admins and super admins. can only be accessed by admins
    """

    try:
        #logic to check if the user is a super admin
        
        async with get_connection() as conn:
            row = await conn.fetch(
                "SELECT fullname,email,role FROM users WHERE role = 'admin' OR role = 'super-admin'"
            )

        return row 
    except (Exception) as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching admins")

class RoleChangeRequest(BaseModel):
    email: str
    role: str


@router.patch("/change_role")
async def change_user_role(
    email: str = None,
    role: str = None,
    current_user: dict = Depends(require_role("admin", "super-admin")),
):
    """
    Change the role of a user. can only be accessed by admins
    email of the user whose role needs to be changed
    """
    try:
        print(email,role)
        if role == 'superadmin':
            role = 'super-admin'

        valid_roles = ["reader", "admin", "super-admin"]
        if role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        async with get_connection() as conn:
            # First check if user exists
            user = await conn.fetchrow(
                "SELECT user_id, fullname FROM users WHERE email = $1",
                email,
            )
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Update user role
            updated_user = await conn.fetchrow(
                "UPDATE users SET role = $1 WHERE email = $2 RETURNING fullname",
                role,
                email,
            )

        if updated_user:
            return {"message": f"User role updated to {role} successfully", "fullname": updated_user['fullname']}
        else:
            raise HTTPException(status_code=404, detail="Failed to update user role")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while changing user role: " + str(e))



class PromoteUserRequest(BaseModel):
    email: str
    role: str = "admin"


@router.post("/promote_user")
async def promote_user(
    payload: Optional[PromoteUserRequest] = Body(None),
    email: Optional[str] = None,
    role: Optional[str] = None,
    current_user: dict = Depends(require_role("admin", "super-admin")),
):
    """
    Promote a user to admin or super-admin. Alias for change_role with better naming.
    """
    if payload is None:
        if email is None or role is None:
            raise HTTPException(status_code=400, detail="email and role are required")
        payload = PromoteUserRequest(email=email, role=role)

    return await change_user_role(payload)
    

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
    
class Update_book_request(BaseModel):
    request_id: str
    status: str
    book_id: str
    reader_id: str
    reader_email: str
    reader_name:str
    decline_reason: Optional[str] = None

@router.put("/update_book_request")
async def update_book_request(
    update_book_request: Update_book_request,
    current_user: dict = Depends(require_role("admin", "super-admin"))
    ):
    """
    Update the status of a book request. can only be accessed by admins
    """
    try:
        request_id = update_book_request.request_id
        status = update_book_request.status
        book_id = update_book_request.book_id
        reader_id = update_book_request.reader_id
        reader_email = update_book_request.reader_email 
        reader_name = update_book_request.reader_name
        decline_reason= update_book_request.decline_reason

        #add logic to check user
        async with get_connection() as conn:
            book_details= await conn.fetch(
                "SELECT * FROM books WHERE book_id = $1",
                book_id
            )
            if (status == "paid" ):
                
                reader_book = {
                    "book_id": book_id,
                    "user_id": reader_id,
                    "current_page": 1,
                    "total_pages": book_details[0]["pages"],
                    "current_chapter_index":1,
                  
                }
                row2 = await conn.fetch(
                    """INSERT INTO readers_books (
                        book_id, 
                        user_id, 
                        current_page, 
                        total_pages, 
                        current_chapter_index
                    ) 
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING reader_book_id;
                    """,
                    reader_book["book_id"],
                    reader_book["user_id"],
                    reader_book["current_page"],
                    reader_book["total_pages"],
                    reader_book["current_chapter_index"]
                )
            row = await conn.fetch(
                "UPDATE book_requests SET status = $1, decline_reason = $3 WHERE request_id = $2 RETURNING *",
                status,
                request_id,
                decline_reason
            )
       
        if row:
            email_status = "accept_request" if status == "paid" else "decline_request"
            #send reader email
            send_email(reader_email,email_status,reader_email,book_details[0]["book_name"]) 
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

@router.get("/admin_books")
async def get_admin_books(admin_id:str):
    """Get a list of all books uploaded by a user. can only be accessed by admins"""
    try:
        #add logic to check user
        async with get_connection() as conn:
            row = await conn.fetch(
                "SELECT * FROM books WHERE admin_id = $1",
                admin_id
            ) 
        return row
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching admin books: " + str(e))
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
       
        async with get_connection() as conn:
            row = await conn.fetch(
                "INSERT INTO book_requests (book_id, admin_id, reader_id, reader_name, reader_email, book_name, book_price,status) VALUES ($1, $2, $3, $4, $5, $6, $7,$8) RETURNING *",
                book_request.book_id,
                book_request.admin_id,
                book_request.reader_id,
                book_request.reader_name,
                book_request.reader_email,
                book_request.book_name,
                book_request.book_price,
                "pending"
            )
            row2 = await conn.fetch(
                "SELECT email,fullname FROM users WHERE user_id = $1",
                book_request.admin_id
            )

        if row:
            send_email(row2[0]["email"], "send_request", user_name=row2[0]["fullname"], book_title=book_request.book_name)
            # send_email(current_user["email"], "confirm_request", user_name=book_request.reader_name, book_title=book_request.book_name)
            return {"message": "Book request sent successfully","new_request":row}
        else:
            raise HTTPException(status_code=404, detail="Book not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while sending book request: " + str(e))

@router.get('/admin_book_report')
async def get_book_report(
    book_id: str,
    current_user: dict = Depends(require_role("admin", "super-admin"))

):
    try:
        #add logic to check user
        async with get_connection() as conn:
            requests = await conn.fetch(
                """
                SELECT reader_name, reader_email, status
                FROM book_requests
                WHERE book_id = $1
                """,
                book_id
            )
            
            readers = await conn.fetch(
                """
                SELECT u.fullname AS reader_name, u.email AS reader_email, rb.progress
                FROM readers_books rb
                JOIN users u ON rb.user_id = u.user_id
                WHERE rb.book_id = $1
                """,
                book_id
            )
        
        pending_list = [{"name": r["reader_name"], "email": r["reader_email"]} for r in requests if r["status"] == "pending"]
        accepted_list = [{"name": r["reader_name"], "email": r["reader_email"]} for r in requests if r["status"] == "paid"]
        declined_list = [{"name": r["reader_name"], "email": r["reader_email"]} for r in requests if r["status"] == "declined"]
        
        completed_list = [{"name": r["reader_name"], "email": r["reader_email"]} for r in readers if r["progress"] == "done"]
        in_progress_list = [{"name": r["reader_name"], "email": r["reader_email"]} for r in readers if r["progress"] == "in_progress"]
        
        return {
            "totalRequests": len(requests),
            "acceptedRequests": len(accepted_list),
            "declinedRequests": len(declined_list),
            "readersDone": len(completed_list),
            "readersReading": len(in_progress_list),
            "pendingList": pending_list,
            "acceptedList": accepted_list,
            "declinedList": declined_list,
            "completedList": completed_list,
            "inProgressList": in_progress_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching admin books: " + str(e))



from services.email_service import send_email as service_send_email

def send_email(
    email: str = "becalisjohnson@gmail.com",
    reason: str = "update_request",
    user_name: str = "James",
    book_title: str = "Sample Book"
):
    success = service_send_email(email, reason=reason, user_name=user_name, book_title=book_title)
    
    if success:
        return {"status": "success", "message": "Email sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")

