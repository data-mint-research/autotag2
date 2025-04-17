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

# Create necessary directories
os.makedirs(config['paths']['input_folder'], exist_ok=True)
os.makedirs(config['paths']['output_folder'], exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="AUTO-TAG API", description="AI-powered image tagging system")

# Set up environment
setup_environment()

@app.post("/process/image")
async def process_single_image(file: UploadFile = File(...), tag_mode: str = "append"):
    """Process a single image and return the generated tags"""
    # Save uploaded file
    input_path = os.path.join(config['paths']['input_folder'], file.filename)
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Process the image
    result = process_image(input_path)
    
    if result["success"]:
        # Write tags to file
        tags = result["tags"]
        success = write_tags_to_file(input_path, tags, tag_mode)
        
        # Return results
        return {
            "success": success,
            "filename": file.filename,
            "tags": tags,
            "processing_time": result["processing_time"]
        }
    else:
        return JSONResponse(
            status_code=400, 
            content={"success": False, "error": result.get("error", "Unknown error")}
        )

@app.post("/process/folder")
async def process_folder(background_tasks: BackgroundTasks, path: str, recursive: bool = False):
    """Start processing a folder in the background"""
    if not os.path.exists(path):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Folder not found: {path}"}
        )
    
    from utils import batch_process_folder
    
    # Add the processing task to background tasks
    background_tasks.add_task(batch_process_folder, path, recursive)
    
    return {
        "success": True,
        "message": f"Started processing folder: {path} (recursive: {recursive})",
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