import os
import torch
import yaml
import logging
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logger = logging.getLogger('auto-tag')

# Global variables for batch processing status
_processing_status = {
    "active": False,
    "current_path": "",
    "total_files": 0,
    "processed_files": 0,
    "successful_files": 0,
    "failed_files": 0,
    "start_time": 0,
    "current_file": "",
    "eta_seconds": 0,
    "output_files": [],
    "save_mode": "replace"
}
_status_lock = threading.Lock()

def setup_environment():
    """Set up the environment for processing"""
    # Load configuration
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Optimize CUDA if available
    if torch.cuda.is_available():
        logger.info(f"CUDA is available: {torch.cuda.get_device_name(0)}")
        
        # Enable TensorFloat32 for performance on newer GPUs
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        
        # Set cuDNN to benchmark mode
        torch.backends.cudnn.benchmark = True
        
        # Disable gradient calculation for inference
        torch.set_grad_enabled(False)
        
        # Pre-allocate some memory to reduce fragmentation
        dummy = torch.zeros(1024, 1024, device='cuda')
        del dummy
        torch.cuda.empty_cache()
    else:
        logger.warning("CUDA is not available, using CPU mode")

def find_images(folder_path: str, recursive: bool = False) -> List[str]:
    """Find all images in a folder"""
    if not os.path.exists(folder_path):
        logger.error(f"Folder not found: {folder_path}")
        return []
    
    image_extensions = {'.jpg', '.jpeg', '.png'}
    image_files = []
    
    if recursive:
        # Recursive search
        for root, _, files in os.walk(folder_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(root, file))
    else:
        # Non-recursive search
        for file in os.listdir(folder_path):
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(os.path.join(folder_path, file))
    
    return image_files

def batch_process_folder(folder_path: str, recursive: bool = False, save_mode: str = "replace"):
    """
    Process all images in a folder
    
    Args:
        folder_path: Path to the folder containing images
        recursive: Whether to process subfolders recursively
        save_mode: How to save the tagged files - "replace" (overwrite originals) or "suffix" (create new files)
    """
    global _processing_status
    
    with _status_lock:
        # Reset status
        _processing_status["active"] = True
        _processing_status["current_path"] = folder_path
        _processing_status["total_files"] = 0
        _processing_status["processed_files"] = 0
        _processing_status["successful_files"] = 0
        _processing_status["failed_files"] = 0
        _processing_status["start_time"] = time.time()
        _processing_status["current_file"] = ""
        _processing_status["eta_seconds"] = 0
        _processing_status["save_mode"] = save_mode
        _processing_status["output_files"] = []
    
    try:
        # Find all images
        image_files = find_images(folder_path, recursive)
        
        with _status_lock:
            _processing_status["total_files"] = len(image_files)
        
        if not image_files:
            logger.warning(f"No images found in {folder_path}")
            with _status_lock:
                _processing_status["active"] = False
            return
        
        # Process each image
        from tagger import process_image, write_tags_to_file
        
        for image_file in image_files:
            # Update status
            with _status_lock:
                _processing_status["current_file"] = os.path.basename(image_file)
            
            # Process the image
            result = process_image(image_file)
            
            # Write tags if successful
            if result["success"]:
                tags = result["tags"]
                tag_success, output_path = write_tags_to_file(image_file, tags, save_mode=save_mode)
                
                with _status_lock:
                    _processing_status["processed_files"] += 1
                    if tag_success:
                        _processing_status["successful_files"] += 1
                        # Store output path in status
                        _processing_status["output_files"].append(output_path)
                    else:
                        _processing_status["failed_files"] += 1
            else:
                with _status_lock:
                    _processing_status["processed_files"] += 1
                    _processing_status["failed_files"] += 1
            
            # Update ETA
            with _status_lock:
                processed = _processing_status["processed_files"]
                total = _processing_status["total_files"]
                elapsed = time.time() - _processing_status["start_time"]
                
                if processed > 0:
                    time_per_file = elapsed / processed
                    remaining_files = total - processed
                    _processing_status["eta_seconds"] = time_per_file * remaining_files
        
        # Complete
        with _status_lock:
            _processing_status["active"] = False
            _processing_status["current_file"] = ""
            
        logger.info(f"Batch processing completed: {_processing_status['successful_files']}/{_processing_status['total_files']} successful")
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        with _status_lock:
            _processing_status["active"] = False

def get_processing_status():
    """Get the current processing status"""
    with _status_lock:
        return _processing_status.copy()