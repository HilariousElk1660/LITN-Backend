from dotenv import load_dotenv
import os

load_dotenv()

from services.email_service import send_email as service_send_email

def send_email(email, template_name = "", user_name = "Reader", book_title = ""):
    return service_send_email(email, reason=template_name, user_name=user_name, book_title=book_title)

