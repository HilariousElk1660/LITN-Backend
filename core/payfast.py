import os
from dotenv import load_dotenv

load_dotenv()

PAYFAST_MERCHANT_ID = os.environ["PAYFAST_MERCHANT_ID"]
PAYFAST_MERCHANT_KEY = os.environ["PAYFAST_MERCHANT_KEY"]
PAYFAST_PASSPHRASE = os.environ.get("PAYFAST_PASSPHRASE", "")
PAYFAST_MODE = os.environ.get("PAYFAST_MODE", "sandbox")

PAYFAST_URL = (
    "https://sandbox.payfast.co.za/eng/process"
    if PAYFAST_MODE == "sandbox"
    else "https://www.payfast.co.za/eng/process"
)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")

VALID_PAYFAST_IPS = [
    "197.97.145.144",
    "197.97.145.145",
    "41.74.179.194",
    "196.33.227.184",
    "196.33.227.185",
    "197.221.32.68",
]