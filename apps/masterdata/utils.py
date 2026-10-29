"""
Utility helpers for master data: QR code generation and SVG formatting.
"""

import io
import base64
import qrcode


def generate_qr_base64(data_payload):
    """
    Generates a clean base64-encoded PNG QR code from arbitrary data payload.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=2,
    )
    qr.add_data(data_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

