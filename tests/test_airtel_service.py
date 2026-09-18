import unittest

from services.airtel_service import build_auth_headers, build_collection_payload


class AirtelServiceTests(unittest.TestCase):
    def test_build_collection_payload_uses_reference_and_phone_number(self):
        payload = build_collection_payload(
            amount="2500",
            phone_number="256700000001",
            reference="book-purchase-42",
            description="Book payment",
        )

        self.assertEqual(payload["transaction"]["amount"], "2500")
        self.assertEqual(payload["reference"], "book-purchase-42")
        self.assertEqual(payload["subscriber"]["msisdn"], "700000001")
        self.assertEqual(payload["description"], "Book payment")

    def test_build_auth_headers_uses_bearer_token(self):
        headers = build_auth_headers("demo-token")

        self.assertEqual(headers["Authorization"], "Bearer demo-token")
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
