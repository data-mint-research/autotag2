import os
import time
import subprocess
import logging
import torch
import shutil
from typing import Dict, List, Any, Optional, Tuple

from models import get_clip_model, get_yolo_model
from config import get_config

logger = logging.getLogger('auto-tag')

def validate_image(file_content: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validiert, ob die Datei ein gültiges Bild in einem unterstützten Format ist.
    
    Args:
        file_content: Binäre Daten des Bildes
        filename: Name der Datei
        
    Returns:
        Tuple[bool, str]: (Ist gültig, Fehlermeldung falls ungültig)
    """
    # 1. Dateierweiterung prüfen
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
    file_ext = os.path.splitext(filename.lower())[1]
    if file_ext not in valid_extensions:
        return False, f"Ungültiges Dateiformat: {file_ext}. Erlaubte Formate: JPG, JPEG, PNG, GIF, BMP, TIFF, WEBP."
    
    # 2 & 5. Dateiintegrität und Format prüfen
    try:
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError
        
        # Versuchen, das Bild zu öffnen
        try:
            with Image.open(BytesIO(file_content)) as image:
                # Unterstützte Formate
                supported_formats = {'JPEG', 'PNG', 'GIF', 'BMP', 'TIFF', 'WEBP'}
                
                # Format überprüfen
                if image.format not in supported_formats:
                    return False, f"Bildformat nicht unterstützt: {image.format}. Unterstützte Formate: {', '.join(supported_formats)}."
                
                # Erzwinge das Laden des Bildes, um sicherzustellen, dass es gültig ist
                image.load()
                
                return True, ""
        except UnidentifiedImageError:
            return False, "Die Datei konnte nicht als Bild identifiziert werden."
            
    except Exception as e:
        return False, f"Ungültiges oder beschädigtes Bild: {str(e)}"

def process_image(image_path: str) -> Dict[str, Any]:
    """Process a single image
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Dict with processing results
    """
    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        return {"success": False, "error": "Image file not found"}

    logger.info(f"Processing image: {os.path.basename(image_path)}")
    start_time = time.time()
    
    try:
        # Verify image integrity
        with open(image_path, 'rb') as f:
            file_content = f.read()
        
        is_valid, error_message = validate_image(file_content, os.path.basename(image_path))
        if not is_valid:
            logger.error(f"Invalid image: {error_message}")
            return {"success": False, "error": error_message}
        
        # Get models
        clip_model = get_clip_model()
        yolo_model = get_yolo_model()
        
        # Analyze with CLIP model
        clip_result = clip_model.analyze(image_path)
        
        # Count people with YOLOv8 model
        people_result = yolo_model.count_people(image_path)
        
        # Generate tags
        tags = generate_tags(clip_result, people_result)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Return results
        return {
            "success": True,
            "tags": tags,
            "clip_result": clip_result,
            "people_result": people_result,
            "processing_time": processing_time
        }
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def generate_tags(clip_result, people_result):
    """Generate tags from model results"""
    tags = []
    
    # Add scene tags
    if clip_result and "scene" in clip_result:
        scene_tag, confidence = clip_result["scene"]
        tags.append(f"scene/{scene_tag}")
    
    # Add room type tags (for indoor scenes)
    if clip_result and "roomtype" in clip_result:
        room_tag, confidence = clip_result["roomtype"]
        tags.append(f"roomtype/{room_tag}")
    
    # Add clothing tags
    if clip_result and "clothing" in clip_result:
        clothing_tag, confidence = clip_result["clothing"]
        tags.append(f"clothing/{clothing_tag}")
    
    # Add people count tags
    if people_result:
        tags.append(f"people/{people_result}")
    
    return tags

def write_tags_to_file(image_path: str, tags: List[str], mode: str = "append", save_mode: str = "replace", timeout: int = 30) -> Tuple[bool, str]:
    """Write tags to image file using ExifTool
    
    Args:
        image_path: Path to the image file
        tags: List of tags to write
        mode: Tag writing mode ("append" or "overwrite")
        save_mode: How to save the file ("replace" original or create "_tagged" suffix)
        timeout: Timeout in seconds for the exiftool process
        
    Returns:
        Tuple[bool, str]: (success status, output file path)
    """
    config = get_config()
    timeout = config.get("tagging", {}).get("exiftool_timeout", 30)
    
    if not tags:
        logger.warning(f"No tags to write to {os.path.basename(image_path)}")
        return True, image_path
    
    try:
        # Format tags as a comma-separated list
        tag_list = ",".join(tags)
        
        # Determine the output path based on save_mode
        if save_mode == "suffix":
            # Create a new file with _tagged suffix
            base_name, ext = os.path.splitext(image_path)
            output_path = f"{base_name}_tagged{ext}"
            
            # Copy the original file
            shutil.copy2(image_path, output_path)
            target_path = output_path
        else:  # replace
            target_path = image_path
        
        # Build the ExifTool command
        if mode == "overwrite":
            cmd = [
                "exiftool",
                f"-XMP-digiKam:TagsList={tag_list}",
                "-overwrite_original",
                target_path
            ]
        else:  # append
            cmd = [
                "exiftool",
                f"-XMP-digiKam:TagsList+={tag_list}",
                "-overwrite_original",
                target_path
            ]
        
        # Execute the command with timeout
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
        
        # Check the result
        if result.returncode != 0:
            logger.error(f"ExifTool error: {result.stderr}")
            return False, image_path
        
        logger.info(f"Successfully wrote {len(tags)} tags to {os.path.basename(target_path)}")
        return True, target_path
            
    except subprocess.TimeoutExpired:
        logger.error(f"ExifTool process timed out after {timeout} seconds for {image_path}")
        return False, image_path
    except Exception as e:
        logger.error(f"Error writing tags to {image_path}: {e}", exc_info=True)
        return False, image_path