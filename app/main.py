#!/usr/bin/env python3
import os
import yaml
import uvicorn
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
import logging
from pathlib import Path

from tagger import process_image, write_tags_to_file
from utils import setup_environment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('auto-tag')

# Load configuration
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize environment

# Initialize FastAPI app
app = FastAPI(title="AUTO-TAG API", description="AI-powered image tagging system")

# Set up environment
setup_environment()

@app.post("/process/image")
async def process_single_image(
    file: UploadFile = File(...),
    tag_mode: str = "append",
    save_mode: str = "replace"
):
    """
    Process a single image and return the generated tags
    
    Args:
        file: The image file to process
        tag_mode: Tag writing mode ("append" or "overwrite")
        save_mode: How to save the tagged file - "replace" (overwrite original) or "suffix" (create new file)
    
    Returns:
        JSON response with tags and file info including output file path
    """
    # Save uploaded file to a temporary location
    import tempfile
    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, file.filename)
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Process the image
    result = process_image(input_path)
    
    if result["success"]:
        # Write tags to file
        tags = result["tags"]
        success, output_path = write_tags_to_file(input_path, tags, tag_mode, save_mode)
        
        # Return results with output path information
        return {
            "success": success,
            "filename": file.filename,
            "output_path": output_path,
            "tags": tags,
            "save_mode": save_mode,
            "processing_time": result["processing_time"]
        }
    else:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": result.get("error", "Unknown error")}
        )

@app.post("/process/folder")
async def process_folder(
    background_tasks: BackgroundTasks,
    path: str,
    recursive: bool = False,
    save_mode: str = "replace"
):
    """
    Start processing a folder in the background
    
    Args:
        background_tasks: FastAPI background tasks
        path: Path to the folder containing images
        recursive: Whether to process subfolders recursively
        save_mode: How to save the tagged files - "replace" (overwrite originals) or "suffix" (create new files)
    
    Returns:
        JSON response with processing status
    """
    if not os.path.exists(path):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Folder not found: {path}"}
        )
    
    from utils import batch_process_folder
    
    # Add the processing task to background tasks
    background_tasks.add_task(batch_process_folder, path, recursive, save_mode=save_mode)
    
    return {
        "success": True,
        "message": f"Started processing folder: {path} (recursive: {recursive}, save_mode: {save_mode})",
        "status_endpoint": "/status"
    }

@app.get("/status")
async def get_status():
    """Get the current processing status"""
    from utils import get_processing_status
    
    return get_processing_status()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)