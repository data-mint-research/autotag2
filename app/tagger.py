import os
import time
import subprocess
import logging
import torch
from typing import Dict, List, Any, Optional

from models import get_clip_model, get_yolo_model

logger = logging.getLogger('auto-tag')

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
        logger.error(f"Error processing image: {e}")
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

def write_tags_to_file(image_path: str, tags: List[str], mode: str = "append") -> bool:
    """Write tags to image file using ExifTool
    
    Args:
        image_path: Path to the image file
        tags: List of tags to write
        mode: Tag writing mode ("append" or "overwrite")
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not tags:
        logger.warning(f"No tags to write to {os.path.basename(image_path)}")
        return True
    
    try:
        # Format tags as a comma-separated list
        tag_list = ",".join(tags)
        
        # Build the ExifTool command
        if mode == "overwrite":
            cmd = [
                "exiftool",
                f"-XMP-digiKam:TagsList={tag_list}",
                "-overwrite_original",
                image_path
            ]
        else:  # append
            cmd = [
                "exiftool",
                f"-XMP-digiKam:TagsList+={tag_list}",
                "-overwrite_original",
                image_path
            ]
        
        # Execute the command
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        # Check the result
        if result.returncode != 0:
            logger.error(f"ExifTool error: {result.stderr}")
            return False
        
        logger.info(f"Successfully wrote {len(tags)} tags to {os.path.basename(image_path)}")
        return True
            
    except Exception as e:
        logger.error(f"Error writing tags to {image_path}: {e}")
        return False