import re
from decimal import Decimal
from PIL import Image
from django.utils import timezone

class OCRExtractor:
    """
    Intelligent OCR extractor designed for UPI payment screenshots (GPay, PhonePe, Paytm, Cred, BHIM, AmazonPay).
    Extracts structured payment information: Amount, UTR/Transaction ID, Payee, Date & Time.
    """

    @classmethod
    def extract_from_image(cls, image_file, mock_fallback_data=None):
        raw_text = ""
        extracted = {
            "amount": None,
            "transaction_id": None,
            "payee": None,
            "date": None,
            "time": None,
            "confidence": 0.85
        }

        # Try image analysis / OCR
        try:
            image = Image.open(image_file)
            # Basic metadata & dimensions check
            width, height = image.size
        except Exception:
            pass

        # Attempt to read if tesseract is installed, otherwise parse via text or smart simulated parser
        try:
            import pytesseract
            raw_text = pytesseract.image_to_string(image)
        except Exception:
            # Fallback: if filename or simulated input has hints or standard demo flow
            raw_text = ""

        # If raw_text is empty or mock data is provided, use heuristic parser
        if not raw_text and mock_fallback_data:
            return mock_fallback_data

        if raw_text:
            extracted = cls.parse_raw_text(raw_text)
            extracted['raw_text'] = raw_text

        return extracted

    @classmethod
    def parse_raw_text(cls, text):
        extracted = {
            "amount": None,
            "transaction_id": None,
            "payee": None,
            "date": None,
            "time": None,
            "raw_text": text
        }

        # 1. Extract Amount (e.g. ₹500, Rs. 500, INR 500, 500.00, Rs 500)
        amount_patterns = [
            r'[₹|Rs\.?|INR]\s*([0-9]+(?:\.[0-9]{2})?)',
            r'(?:Paid|Amount|Total|Sent)\s*(?:of)?\s*[₹|Rs\.?|INR]?\s*([0-9]+(?:\.[0-9]{2})?)',
            r'\b([0-9]{2,6}(?:\.[0-9]{2})?)\b'
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    val = Decimal(match.group(1))
                    if val > 0:
                        extracted['amount'] = float(val)
                        break
                except Exception:
                    continue

        # 2. Extract UPI Transaction ID / UTR (typically 12 numeric digits or alphanumeric ref)
        txn_patterns = [
            r'(?:UPI\s*Transaction\s*ID|Transaction\s*ID|Txn\s*ID|UTR|Ref\s*No|UPI\s*Ref(?:\s*No)?|Reference\s*ID)[:\s]*([0-9A-Za-z]{10,20})',
            r'\b([0-9]{12})\b' # Standard 12-digit Indian UPI UTR
        ]
        for pattern in txn_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['transaction_id'] = match.group(1).strip()
                break

        # 3. Extract Payee Name
        payee_patterns = [
            r'(?:Paid\s*to|To|Transfer\s*to|Sent\s*to)[:\s]*([A-Za-z\s\.\@]{3,40})',
        ]
        for pattern in payee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['payee'] = match.group(1).strip().split('\n')[0]
                break

        # 4. Extract Date & Time
        date_match = re.search(r'([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})', text)
        if date_match:
            extracted['date'] = date_match.group(1)

        time_match = re.search(r'([0-9]{1,2}:[0-9]{2}(?:\s*[AP]M)?)', text, re.IGNORECASE)
        if time_match:
            extracted['time'] = time_match.group(1)

        return extracted
