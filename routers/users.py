from dotenv import load_dotenv
import os

load_dotenv()

def send_email(email,template_name = ""):
    import resend   
    resend.api_key = os.getenv("RESEND_API_KEY")

    subjects = {
        "update_request": "Your book request payment has been reviewed",
        "send_request": "New book request",
        "confirm_request":"Your book request has been confirmed"
    }
    r = resend.Emails.send({
    "from": "bookapp@shoenationrsa.com",
    "to": email,
    "subject": subjects[template_name],
    "html":"<h1>Hello World</h1>"
    # "template": {
    # "id": template_name,
    # "variables": {
    #   "PRODUCT": "Vintage Macintosh",
    #   "PRICE": 499
    # }
    # }
    })

