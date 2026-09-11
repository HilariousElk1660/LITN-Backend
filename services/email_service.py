import os
import requests
from dotenv import load_dotenv

load_dotenv()

service_id = os.getenv("EMAIL_JS_SERVICE_ID")
template_id = os.getenv("EMAIL_JS_TEMPLATE_ID")
public_key = os.getenv("EMAIL_JS_PUBLIC_KEY")

def send_email(email: str, reason: str, user_name: str = "Reader", book_title: str = ""):
    """
    Renders the email HTML template and sends it via Resend.
    """
    # 1. Define subjects
    subjects = {
        "decline_request":"Your book request payment has been reviewed",
        "accept_request": "Your book request payment has been reviewed",
        "send_request": "New book request",
        "confirm_request": "Your book request has been confirmed",
        "payfast_confirmation": "Your PayFast payment was successful"
    }
    
    if reason not in subjects:
        print(f"Unknown email reason/template: {reason}")
        return False

    # 2. Define dynamic contents
    email_content = {
        "accept_request": {
            "heading": "Your subscription has been approved!",
            "par1": f"Your book request payment for '{book_title}'",
            "par2": "We are thrilled to let you know that your subscription request has been reviewed and successfully approved by our administrator team. You now have full access to dive into the novel, explore all chapters, highlight your favorite passages, and keep track of your reading progress.",
        },
        "decline_request": {
            "heading": "Your subscription has been rejected",
            "par1": f"Your book request payment for '{book_title}'",
            "par2": "We're sorry to let you know that your subscription request has been reviewed and was not approved by our administrator team. You won't have access to this novel at this time, but you're welcome to explore other titles in our library or reach out to our support team if you have any questions about this decision."
        },
        "send_request": {
            "heading": "New book request",
            "par1": f"A new book request has been submitted for '{book_title}'",
            "par2": "Our team has received your request and we are currently processing the payment. We will notify you once your subscription is approved.",
        },
        "confirm_request": {
            "heading": "Your book request has been confirmed",
            "par1": f"Your book request for '{book_title}'",
            "par2": "Your request is confirmed and will be available in your library very soon. Thank you for using our service!",
        },
        "payfast_confirmation": {
        "heading": "Payment received — you're all set!",
        "par1": f"Your PayFast payment for '{book_title}' was successful",
        "par2": "Thank you for your payment. Your subscription is now active and the book has been added to your library — happy reading!",
        }
    }
    
    content = {**email_content[reason],"user_name":user_name,"email":email, "subject": subjects[reason]}
    
    data = {
    'service_id': service_id,
    'template_id': template_id,
    'user_id': public_key,
    'accessToken': 'c-YmMGn02dXa1y4FDAFhw',
    'template_params': content,
}

    try:
        response = requests.post(
            'https://api.emailjs.com/api/v1.0/email/send',
            json=data  # requests handles JSON serialization + content-type header
        )
        response.raise_for_status()  # raises an exception for 4xx/5xx responses
        print('Your mail is sent!')
        return "success"
    except requests.exceptions.RequestException as error:
        print(f'Oops... {error}')
        return None
