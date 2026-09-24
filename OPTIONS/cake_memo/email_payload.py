"""Cake Memo Email Payload Generator: Outlook draft creation for cake service notifications."""

from typing import Dict

from MODULES.common.fb_email_recipients import TO_RECIPIENTS, CC_RECIPIENTS


def generate_cake_memo_outlook_payload(docx_path: str, memo_data: Dict[str, str]) -> dict:
    """Generates an Outlook draft payload with the specified recipients, subject, and formatted HTML body."""

    room_number = memo_data["room_number"]
    cake_date = memo_data["cake_date_display"]
    cake_location = memo_data["cake_location"]
    cake_time = memo_data["cake_time"]

    subject = f"CAKE MEMO {cake_date} R{room_number}"

    html_body = f"""<div style='font-family: Calibri, sans-serif; font-size: 11pt;'>
  Dear all,<br>Kindly find attached the Cake Memo for Room {room_number}.<br><br>
  <b>Service Details:</b><br>
  &bull; <b>Date:</b> {cake_date}<br>
  &bull; <b>Location:</b> {cake_location}<br>
  &bull; <b>Time:</b> {cake_time}<br><br>
  For any further information don't hesitate to contact the Guest Relations Team.
</div>"""

    return {
        "type": "outlook_draft",
        "category": "Offer",
        "subcategory": "Cake Memo",
        "room_number": room_number,
        "is_service_trace": True,
        "data": {
            "To": TO_RECIPIENTS,
            "CC": CC_RECIPIENTS,
            "Subject": subject,
            "HTMLBody": html_body,
            "Attachment": docx_path
        }
    }
