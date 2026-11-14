"""HTML templates for workflow emails."""

from html import escape


def challan_payment_email(amount: str, challan_number: str) -> str:
    """Render the payment instructions; the QR is sent as an attachment."""
    return f"""\
<!DOCTYPE html>
<html><body style="font-family: Arial, sans-serif; color: #172033;">
  <h2>Challan payment</h2>
  <p>Your UPI payment QR code is attached.</p>
  <p><strong>Challan number:</strong> {escape(challan_number)}</p>
  <p><strong>Amount:</strong> ₹{escape(amount)}</p>
  <p>Open your UPI app and scan the attached QR code to complete the payment.</p>
  <p>The QR code may expire. Generating it does not confirm payment.</p>
</body></html>"""
