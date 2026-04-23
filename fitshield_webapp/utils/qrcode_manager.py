from io import BytesIO
import os
import re
from urllib.parse import urlencode
from django.conf import settings
import qrcode
from config.s3_connection import s3_client, bucket_name


def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    return qr_img


def generate_qr_with_text(data, text):
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    # Generate QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Set up font
    try:
        font = ImageFont.truetype("/content/Arial.ttf", size=30)
    except OSError:
        font = ImageFont.load_default()

    # Calculate text position
    qr_width, qr_height = qr_img.size
    draw = ImageDraw.Draw(qr_img)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Create a new image with enough space for text
    padding = 30
    new_height = qr_height + text_height + padding
    combined_img = Image.new("RGB", (qr_width, new_height), "white")
    combined_img.paste(qr_img, (0, 0))

    # Draw text below the QR code
    draw = ImageDraw.Draw(combined_img)
    text_position = ((qr_width - text_width) // 2, qr_height + (padding // 2))
    draw.text(text_position, text, fill="black", font=font)

    return combined_img
    
def sanitize_file_name(file_name):
    """Sanitize file names to avoid invalid characters."""
    return re.sub(r'[<>:"/\\|?*]', '_', file_name)

def generate_qr_code(restro_id, table_number, floor_name, force_regenerate=False):
    query_params = {
        "restro_id": restro_id,
        "table_number": table_number,
        "floor_name": floor_name,
        "regenerate": str(force_regenerate).lower(),
        "joined_group": str(False).lower()

    }
    qr_code_data = f"{settings.BASE_URL}?{urlencode(query_params)}"
    
    # Sanitize the file name and construct the file path
    file_name = f"res_{restro_id}_{floor_name}_table_{table_number}.jpg"
    file_name = sanitize_file_name(file_name)    

    qr_s3_file_path = f"restaurants/{restro_id}/QR_Codes/{file_name}"
    # Generate QR code with text below
    qr_img_with_text = generate_qr_with_text(qr_code_data, f"Table {table_number}")

    # Generate QR code image
    # qr_img = qrcode.make(qr_code_data)
    file_obj = BytesIO()
    qr_img_with_text.save(file_obj, format="JPEG")
    file_obj.seek(0)

    # Upload to S3
    s3_client.upload_fileobj(
        file_obj,
        bucket_name,
        qr_s3_file_path,
        ExtraArgs={"ContentType": "image/jpeg"}
    )

    # Return the S3 file URL
    qr_url = f"https://{bucket_name}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{qr_s3_file_path}"
    return qr_url


def generate_group_qr_code(restro_id,group_id,table_number, floor_name, force_regenerate=False):
    # Define the base URL for the QR code
    # base_url = "http://app.fitshield.in/#/menu-selection"  # Replace with your actual base URL
    base_url = "http://app.fitshield.in/#/splash"  # Replace with your actual base URL

    query_params = {
        "group_id": group_id,
        "restro_id": restro_id,
        "floor_name": floor_name,
        "table_number": table_number, 
        "joined_group": str(True).lower()
    }
    qr_code_data = f"{base_url}?{urlencode(query_params)}"

    # Sanitize the file name
    file_name = f"group_{group_id}_restro_{restro_id}.jpg"
    file_name = sanitize_file_name(file_name)

    qr_s3_file_path = f"Group_QR_Codes/{file_name}"
    # Generate QR code with text below
    qr_img_with_text = generate_qr_with_text(qr_code_data, f"Table {table_number}")

    # Generate QR code image
    # qr_img = qrcode.make(qr_code_data)
    file_obj = BytesIO()
    qr_img_with_text.save(file_obj, format="JPEG")
    file_obj.seek(0)

    # Upload to S3
    s3_client.upload_fileobj(
        file_obj,
        bucket_name,
        qr_s3_file_path,
        ExtraArgs={"ContentType": "image/jpeg"}
    )

    # Return the S3 file URL
    qr_url = f"https://{bucket_name}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{qr_s3_file_path}"
    return qr_url