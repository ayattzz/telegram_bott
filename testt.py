import os

file_path = "payment_qr.png"
if os.path.exists(file_path):
    print("QR code generated successfully.")
else:
    print("QR code generation failed.")
