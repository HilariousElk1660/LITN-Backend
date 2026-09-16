import os
import requests
from dotenv import load_dotenv

load_dotenv()

service_id = os.getenv("EMAIL_JS_SERVICE_ID")
template_id = os.getenv("EMAIL_JS_TEMPLATE_ID")
public_key = os.getenv("EMAIL_JS_PUBLIC_KEY")

def send_email(email: str, reason: str, user_name: str = "Reader", book_title: str = "", reset_url: str = ""):
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
    # Add password reset subject
    subjects["reset_password"] = "Reset your LITN password"
    
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
    # Add reset password template vars
    email_content["reset_password"] = {
        "heading": "Reset your password",
        "par1": "We received a request to reset your password.",
        "par2": "Click the link below to choose a new password. If you didn't request this, you can ignore this email.",
        "reset_url": reset_url,
    }
    
    content = {**email_content[reason], "user_name": user_name, "email": email, "subject": subjects[reason]}
    
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
        # If this is a reset email, also send a plain HTML/text email via Resend
        resend_key = os.getenv("RESEND_API_KEY")
        if reason == "reset_password" and resend_key and reset_url:
            try:
                resend_html = f"""
<div style="font-family: Arial, sans-serif; color: #111;">
  <h2>Reset your password</h2>
  <p>Hello {user_name},</p>
  <p>We received a request to reset your password. Click the button below to choose a new password.</p>
  <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
    <tr>
      <td align="center" bgcolor="#0ea5a4" style="border-radius:6px;">
        <a href="{reset_url}"
           target="_blank"
           style="display:inline-block;padding:12px 24px;font-size:16px;font-weight:bold;
                  color:#ffffff;background:#0ea5a4;border-radius:6px;text-decoration:none;
                  font-family: Arial, sans-serif;">
          Reset Password
        </a>
      </td>
    </tr>
  </table>
  <p>If the button doesn't work, paste this link into your browser:</p>
  <p style="font-size:12px;color:#666;word-break:break-all">{reset_url}</p>
</div>
"""

                resend_payload = {
                    "from": "LITN <no-reply@litn.app>",
                    "to": [email],
                    "subject": subjects[reason],
                    "html": resend_html,
                }

                r = requests.post(
                    "https://api.resend.com/emails",
                    json=resend_payload,
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    timeout=10,
                )
                r.raise_for_status()
                print("Resend: reset email sent")
            except requests.exceptions.RequestException as err:
                print(f"Resend failed: {err}")

        return "success"
    except requests.exceptions.RequestException as error:
        print(f'Oops... {error}')
        return None
