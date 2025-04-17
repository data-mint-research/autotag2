#!/usr/bin/env python3
"""
Model Downloader Script

This script downloads the necessary AI models for AUTO-TAG.
It creates a models directory with the required model files.
"""

import os
import sys
import requests
import hashlib
from pathlib import Path
from tqdm import tqdm
import argparse

# Model URLs and information
MODELS = {
    "clip": {
        "filename": "clip_vit_b32.pth",
        "url": "https://github.com/openai/CLIP/releases/download/v1.0/clip_vit_b32.pth",
        "size": 354355280,
        "sha256": "a4ccb0c288dd8c53e8ef99417d08e3731ecf29c9e39297a45f37c56e5366ca6e"
    },
    "yolov8": {
        "filename": "yolov8n.pt",
        "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
        "size": 6246000,
        "sha256": "6dbb68b8a5d19992f5a5e3b99d1ba466893dcf618bd5e8c0fe551705eb1f6315"
    },
    "facenet": {
        "filename": "facenet_model.pth",
        "url": "https://github.com/timesler/facenet-pytorch/releases/download/v2.5.2/20180402-114759-vggface2.pt",
        "size": 89456789,
        "sha256": "5e4c2578ffeff9e1dde7d0d10e025c4319b13e4d058577cf430c8df5cf613c45"
    }
}

def calculate_sha256(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 1MB chunks
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def download_file(url, destination, expected_size=None):
    """Download a file with progress bar"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get file size for progress bar
        total_size = int(response.headers.get('content-length', 0))
        if not total_size and expected_size:
            total_size = expected_size
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # Download with progress bar
        with open(destination, 'wb') as f, tqdm(
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc=os.path.basename(destination)
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
        
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        if os.path.exists(destination):
            os.remove(destination)
        return False

def verify_model(file_path, expected_hash):
    """Verify the hash of a downloaded model file"""
    print(f"Verifying {os.path.basename(file_path)}...")
    actual_hash = calculate_sha256(file_path)
    if actual_hash != expected_hash:
        print(f"Hash verification failed for {file_path}")
        print(f"Expected: {expected_hash}")
        print(f"Got:      {actual_hash}")
        return False
    
    print(f"Hash verification successful for {os.path.basename(file_path)}")
    return True

def download_models(output_dir):
    """Download all models to the specified output directory"""
    os.makedirs(output_dir, exist_ok=True)
    
    success = True
    for model_name, model_info in MODELS.items():
        # Create model-specific directory
        model_dir = os.path.join(output_dir, model_name)
        os.makedirs(model_dir, exist_ok=True)
        
        # Destination path
        dest_path = os.path.join(model_dir, model_info["filename"])
        
        # Check if file already exists and is valid
        if os.path.exists(dest_path) and os.path.getsize(dest_path) == model_info["size"]:
            if verify_model(dest_path, model_info["sha256"]):
                print(f"Model {model_name} already exists and is valid")
                continue
            
            print(f"Existing model {model_name} is invalid, re-downloading")
            os.remove(dest_path)
        
        # Download the model
        print(f"Downloading {model_name} model...")
        if not download_file(model_info["url"], dest_path, model_info["size"]):
            print(f"Failed to download {model_name} model")
            success = False
            continue
        
        # Verify the downloaded model
        if not verify_model(dest_path, model_info["sha256"]):
            print(f"Verification failed for {model_name} model")
            success = False
            continue
        
        print(f"Successfully downloaded and verified {model_name} model")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="Download AUTO-TAG models")
    parser.add_argument("--output-dir", default="models", help="Output directory for models")
    args = parser.parse_args()
    
    print("AUTO-TAG Model Downloader")
    print("-----------------------")
    
    if download_models(args.output_dir):
        print("\nAll models downloaded and verified successfully!")
        return 0
    else:
        print("\nSome models failed to download or verify.")
        return 1

if __name__ == "__main__":
    sys.exit(main())