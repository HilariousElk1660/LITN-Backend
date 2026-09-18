import os
from dotenv import load_dotenv

load_dotenv()

AIRTEL_ENVIRONMENT = os.getenv("AIRTEL_ENVIRONMENT", "sandbox").strip().lower()
AIRTEL_BASE_URL = os.getenv(
    "AIRTEL_BASE_URL",
    "https://openapiuat.airtel.africa" if AIRTEL_ENVIRONMENT == "sandbox" else "https://openapi.airtel.africa",
)
AIRTEL_CLIENT_ID = os.getenv("AIRTEL_CLIENT_ID", "")
AIRTEL_CLIENT_SECRET = os.getenv("AIRTEL_CLIENT_SECRET", "")
AIRTEL_API_KEY = os.getenv("AIRTEL_API_KEY", "")
AIRTEL_CALLBACK_SECRET = os.getenv("AIRTEL_CALLBACK_SECRET", "")
AIRTEL_COUNTRY = os.getenv("AIRTEL_COUNTRY", "UG").upper()
AIRTEL_CURRENCY = os.getenv("AIRTEL_CURRENCY", "UGX").upper()
