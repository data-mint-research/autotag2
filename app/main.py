#!/usr/bin/env python3
import os
import signal
import sys
import atexit
import time
import tempfile
import yaml
import uvicorn
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import logging
from pathlib import Path

from tagger import process_image, write_tags_to_file, validate_image
from utils import setup_environment, batch_process_folder, get_processing_status, cleanup_resources
from config import get_config

# Konfiguration laden
config = get_config()

# Logger konfigurieren
logger = logging.getLogger('auto-tag')

# Globale Variable für aktuelle Hintergrundaufgaben
active_background_tasks = set()

# Signal Handler für ordnungsgemäßes Herunterfahren
def signal_handler(sig, frame):
    """Behandelt Systemsignale für ordnungsgemäßes Herunterfahren"""
    logger.info(f"Empfangenes Signal: {sig}. Beginne sauberes Herunterfahren...")
    cleanup_resources()
    sys.exit(0)

# Signal-Handler registrieren
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Docker stop

# Registriere Cleanup-Funktion für normales Beenden
atexit.register(cleanup_resources)

# Modelle für Request/Response-Validierung und Dokumentation
class TagMode(str, Enum):
    APPEND = "append"
    OVERWRITE = "overwrite"

class SaveMode(str, Enum):
    REPLACE = "replace"
    SUFFIX = "suffix"

class ProcessingResult(BaseModel):
    success: bool = Field(
        ..., 
        description="Whether the processing was successful"
    )
    filename: Optional[str] = Field(
        None, 
        description="The name of the processed file"
    )
    output_path: Optional[str] = Field(
        None, 
        description="Path to the output file with tags"
    )
    tags: Optional[List[str]] = Field(
        None, 
        description="List of tags added to the image"
    )
    save_mode: Optional[SaveMode] = Field(
        None, 
        description="How the output file was saved"
    )
    processing_time: Optional[float] = Field(
        None, 
        description="Processing time in seconds"
    )
    error: Optional[str] = Field(
        None, 
        description="Error message if processing failed"
    )

class FolderProcessRequest(BaseModel):
    path: str = Field(
        ..., 
        description="Path to the folder containing images to process"
    )
    recursive: bool = Field(
        False, 
        description="Whether to process subfolders recursively"
    )
    save_mode: SaveMode = Field(
        SaveMode.REPLACE, 
        description="How to save the output files: replace original or create new with suffix"
    )

class FolderProcessResponse(BaseModel):
    success: bool = Field(
        ..., 
        description="Whether the folder processing started successfully"
    )
    message: str = Field(
        ..., 
        description="Status message"
    )
    status_endpoint: str = Field(
        "/status", 
        description="Endpoint to check processing status"
    )

class ProcessingStatusStats(BaseModel):
    avg_time_per_image: float = Field(
        0, 
        description="Average processing time per image in seconds"
    )
    fastest_image: Dict[str, Any] = Field(
        {"file": "", "time": 0}, 
        description="Information about the fastest processed image"
    )
    slowest_image: Dict[str, Any] = Field(
        {"file": "", "time": 0}, 
        description="Information about the slowest processed image"
    )

class StatusMessage(BaseModel):
    time: float = Field(
        ..., 
        description="Timestamp of the message"
    )
    file: str = Field(
        ..., 
        description="File associated with the message"
    )
    message: str = Field(
        ..., 
        description="Status message content"
    )

class ProcessingStatus(BaseModel):
    active: bool = Field(
        ..., 
        description="Whether processing is currently active"
    )
    current_path: str = Field(
        "", 
        description="Path to the folder being processed"
    )
    total_files: int = Field(
        0, 
        description="Total number of files to process"
    )
    processed_files: int = Field(
        0, 
        description="Number of files processed so far"
    )
    successful_files: int = Field(
        0, 
        description="Number of files successfully processed"
    )
    failed_files: int = Field(
        0, 
        description="Number of files that failed processing"
    )
    start_time: float = Field(
        0, 
        description="Timestamp when processing started"
    )
    current_file: str = Field(
        "", 
        description="File currently being processed"
    )
    eta_seconds: float = Field(
        0, 
        description="Estimated time remaining in seconds"
    )
    eta_formatted: Optional[str] = Field(
        None, 
        description="Estimated time remaining in human-readable format"
    )
    runtime_formatted: Optional[str] = Field(
        None, 
        description="Total runtime in human-readable format"
    )
    save_mode: SaveMode = Field(
        SaveMode.REPLACE, 
        description="How processed files are being saved"
    )
    progress_percent: float = Field(
        0, 
        description="Current progress as percentage"
    )
    phase: str = Field(
        "", 
        description="Current processing phase"
    )
    recent_status: List[StatusMessage] = Field(
        [], 
        description="Recent status messages"
    )
    errors: List[StatusMessage] = Field(
        [], 
        description="Error messages encountered during processing"
    )
    stats: ProcessingStatusStats = Field(
        ProcessingStatusStats(), 
        description="Processing statistics"
    )

# Initialize FastAPI app
app = FastAPI(
    title="AUTO-TAG API",
    description="""
    AI-powered image tagging system that automatically analyzes images and adds structured metadata tags.
    The system uses multiple AI models to identify various aspects of images, including:
    
    * Scene Classification (indoor/outdoor, room types)
    * Person Detection (solo/group)
    * Clothing Detection
    
    All processing happens within the Docker container, with GPU acceleration when available.
    """,
    version="1.0.0",
    docs_url=None,  # Deaktiviere Standard-Docs-URL für angepasste Swagger UI
    redoc_url=None,  # Deaktiviere Standard-Redoc-URL
    openapi_url="/api/openapi.json"
)

# CORS-Middleware hinzufügen für Dokumentationszugriff
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up environment
setup_environment()

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    """Redirect root to custom docs"""
    return RedirectResponse(url="/docs")

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced styles"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.3.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.3.0/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )

@app.post(
    "/process/image", 
    response_model=ProcessingResult,
    responses={
        200: {
            "description": "Image processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "filename": "vacation.jpg",
                        "output_path": "/app/data/output/vacation.jpg",
                        "tags": ["scene/outdoor", "clothing/dressed", "people/group"],
                        "save_mode": "replace",
                        "processing_time": 2.34
                    }
                }
            }
        },
        400: {
            "description": "Invalid input or processing error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error": "Invalid image format"
                    }
                }
            }
        }
    }
)
async def process_single_image(
    file: UploadFile = File(..., description="The image file to process"),
    tag_mode: TagMode = TagMode.APPEND,
    save_mode: SaveMode = SaveMode.REPLACE
):
    """
    Process a single image and return the generated tags.
    
    This endpoint accepts an image file, processes it using multiple AI models,
    and adds structured metadata tags to the image file.
    
    The AI models will detect:
    - Scene type (indoor/outdoor)
    - Room type (for indoor scenes)
    - People count (solo/group)
    - Clothing status
    
    The tags are written to the XMP-digiKam:TagsList field in the image metadata,
    making them compatible with photo management applications.
    """
    # Datei einlesen
    file_content = await file.read()
    
    # Bildvalidierung durchführen
    is_valid, error_message = validate_image(file_content, file.filename)
    if not is_valid:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": error_message}
        )
    
    # Save uploaded file to a temporary location with proper cleanup
    temp_file = tempfile.NamedTemporaryFile(
        prefix="autotag_",
        suffix=os.path.splitext(file.filename)[1],
        delete=False
    )
    input_path = temp_file.name
    temp_file.write(file_content)
    temp_file.close()
    
    try:
        # Process the image
        result = process_image(input_path)
        
        if result["success"]:
            # Write tags to file
            tags = result["tags"]
            success, output_path = write_tags_to_file(
                input_path, 
                tags, 
                mode=tag_mode, 
                save_mode=save_mode
            )
            
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
    finally:
        # Temporäre Datei aufräumen
        if os.path.exists(input_path):
            try:
                os.unlink(input_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {input_path}: {e}")

@app.post(
    "/process/folder", 
    response_model=FolderProcessResponse,
    responses={
        200: {
            "description": "Folder processing started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Started processing folder: /app/data/input (recursive: false, save_mode: replace)",
                        "status_endpoint": "/status"
                    }
                }
            }
        },
        400: {
            "description": "Invalid folder path",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error": "Folder not found: /nonexistent/path"
                    }
                }
            }
        }
    }
)
async def process_folder(
    background_tasks: BackgroundTasks,
    request: FolderProcessRequest
):
    """
    Start processing a folder in the background.
    
    This endpoint initiates a background task to process all images in the specified folder.
    The processing status can be checked using the /status endpoint.
    
    The folder path should be accessible from within the Docker container. If you're using
    Docker Desktop for Windows, make sure the path is mapped correctly.
    
    For recursive processing, all subfolders will be traversed and images will be processed
    with the same settings.
    """
    if not os.path.exists(request.path):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Folder not found: {request.path}"}
        )
    
    # Task-Tracking für Graceful Shutdown
    task_id = f"folder_{id(request.path)}_{time.time()}"
    active_background_tasks.add(task_id)
    
    # Modifizierte background_tasks.add_task mit Tracking
    async def tracked_batch_process(*args, **kwargs):
        try:
            batch_process_folder(*args, **kwargs)
        finally:
            # Task aus dem Tracking entfernen
            active_background_tasks.discard(task_id)
    
    # Add the processing task to background tasks
    background_tasks.add_task(tracked_batch_process, request.path, request.recursive, save_mode=request.save_mode)
    
    return {
        "success": True,
        "message": f"Started processing folder: {request.path} (recursive: {request.recursive}, save_mode: {request.save_mode})",
        "status_endpoint": "/status"
    }

@app.get(
    "/status", 
    response_model=ProcessingStatus,
    responses={
        200: {
            "description": "Current processing status",
            "content": {
                "application/json": {
                    "example": {
                        "active": True,
                        "current_path": "/app/data/input",
                        "total_files": 100,
                        "processed_files": 45,
                        "successful_files": 43,
                        "failed_files": 2,
                        "progress_percent": 45.0,
                        "current_file": "image045.jpg",
                        "eta_seconds": 120.5,
                        "eta_formatted": "2m 0s",
                        "phase": "processing",
                        # Weitere Statusfelder...
                    }
                }
            }
        }
    }
)
async def get_status():
    """
    Get the current processing status.
    
    This endpoint provides detailed information about the current or most recent
    folder processing operation, including:
    
    - Overall progress and statistics
    - Estimated time remaining
    - Currently processing file
    - Recent status messages and errors
    - Performance statistics
    
    Poll this endpoint to monitor the progress of a folder processing operation.
    """
    return get_processing_status()

# Angepasste OpenAPI-Schema-Generierung
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Zusätzliche Informationen
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    # Server-Information
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        }
    ]
    
    # Zusätzliche Tags und Beschreibungen
    openapi_schema["tags"] = [
        {
            "name": "Image Processing",
            "description": "Endpoints for processing individual images and folders"
        },
        {
            "name": "Status",
            "description": "Endpoints for checking processing status"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    port = int(os.environ.get("AUTOTAG_PORT", config["api"]["port"]))
    host = os.environ.get("AUTOTAG_HOST", config["api"]["host"])
    
    logger.info(f"Starting AUTO-TAG service on {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False)