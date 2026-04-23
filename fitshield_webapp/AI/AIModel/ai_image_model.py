import os
import logging
import time
from bing_image_downloader import downloader
from PIL import Image, ImageFilter
from io import BytesIO
from django.conf import settings
from config.s3_connection import s3_client, bucket_name
import shutil

logger = logging.getLogger(__name__)

def generate_img(restro_id, dish_name):
    def enhance_image(image):
        """Enhances the image quality using a sharpening filter."""
        return image.filter(ImageFilter.SHARPEN)

    def download_and_resize_image(search_term, resize_to=(140, 174)):
        """Downloads and resizes an image using Bing Image Downloader in-memory."""
        try:
            # Use Bing Image Downloader to fetch images
            downloader.download(search_term, limit=1, output_dir=".", adult_filter_off=True, force_replace=False, timeout=60)
            search_dir = os.path.join(".", search_term)

            if os.path.exists(search_dir):
                downloaded_files = os.listdir(search_dir)
                if downloaded_files:
                    for file in downloaded_files:
                        if file.lower().endswith(('png', 'jpg', 'jpeg', 'bmp', 'gif')):
                            original_image_path = os.path.join(search_dir, file)

                            # Open the downloaded image
                            with Image.open(original_image_path) as img:
                                # Resize the image
                                resized_img = img.resize(resize_to)
                                img_buffer = BytesIO()
                                resized_img.save(img_buffer, format="JPEG")
                                img_buffer.seek(0)
                                
                                # Clean up downloaded files and folder
                                shutil.rmtree(search_dir,ignore_errors=True)

                                while os.path.exists(search_dir):
                                    time.sleep(0.5)
                                
                                return img_buffer  # Return the in-memory image buffer

                # Clean up if no valid files
                shutil.rmtree(search_dir)
                while os.path.exists(search_dir):
                    time.sleep(0.5)


        except Exception as e:
            logger.error(f"Error downloading or resizing images for {search_term}: {e}")
        return None

    try:
        # Step 1: Download and resize the image using Bing Image Downloader
        search_query = f"{dish_name} full HD plain plate background"
        downloaded_image_buffer = download_and_resize_image(search_query)

        # Step 2: Handle fallback if no image is downloaded
        if not downloaded_image_buffer:
            logger.warning(f"No images found for the dish: {dish_name}")
            fallback_s3_path = "restaurants/default_restaurant/default_image.png"
            fallback_url = f"https://{bucket_name}.s3.amazonaws.com/{fallback_s3_path}"
            logger.info(f"Using fallback image: {fallback_url}")
            return fallback_url

        # Step 3: Process the downloaded image buffer
        with Image.open(downloaded_image_buffer) as img:
            enhanced_image = enhance_image(img)

            # Prepare S3 path
            file_name = f"{dish_name.replace(' ', '_').lower()}.jpg"
            s3_path = f"restaurants/{restro_id}/dishes/{file_name}"

            # Upload the image to S3
            try:
                with BytesIO() as image_buffer:
                    enhanced_image.save(image_buffer, format="JPEG")
                    image_buffer.seek(0)
                    s3_client.upload_fileobj(image_buffer, bucket_name, s3_path, ExtraArgs={'ContentType': 'image/jpeg'})

                    downloaded_image_buffer.close()


                    
            except Exception as upload_error:
                logger.error(f"Error uploading image to S3: {upload_error}")
                fallback_s3_path = "restaurants/default_restaurant/default_image.png"
                fallback_url = f"https://{bucket_name}.s3.amazonaws.com/{fallback_s3_path}"
                logger.info(f"Using fallback image: {fallback_url}")
                return fallback_url
            
            shutil.rmtree(search_query,ignore_errors=True)
            while os.path.exists(search_query):
                time.sleep(0.5)

            # Generate and return the public URL
            uploaded_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"
            logger.info(f"Image uploaded successfully: {uploaded_url}")
            return uploaded_url

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        # Use fallback image in case of any unexpected errors
        fallback_s3_path = "restaurants/default_restaurant/default_image.png"
        fallback_url = f"https://{bucket_name}.s3.amazonaws.com/{fallback_s3_path}"
        logger.info(f"Using fallback image: {fallback_url}")
        return fallback_url
