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
import time

# Model URLs and information
MODELS = {
    "clip": {
        "filename": "clip_vit_b32.pth",
        "url": "https://openaipublic.azureedge.net/clip/models/40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt",
        "size": 354349880,
        "sha256": "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af"
    },
    "yolov8": {
        "filename": "yolov8n.pt",
        "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
        "size": 6437762,
        "sha256": "31e20dde3def09e2cf938c7be6fe23d9150bbbe503982af13345706515f2ef95"
    },
    "facenet": {
        "filename": "facenet_model.pth",
        "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/facenet.pth",
        "skip_hash_check": True  # Skip hash verification for this model
    }
}

def calculate_sha256(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 1MB chunks for better efficiency
        for byte_block in iter(lambda: f.read(1024*1024), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def download_file(url, destination, expected_size=None, max_retries=3, backup_url=None):
    """Download a file with progress bar and retry mechanism"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=30)  # Timeout hinzugefügt
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
                for chunk in response.iter_content(chunk_size=8192):  # Größere Chunks für Effizienz
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
            
            return True
        except (requests.RequestException, IOError) as e:
            wait_time = 2 ** attempt  # Exponentieller Backoff
            print(f"Download attempt {attempt+1}/{max_retries} failed: {str(e)}")
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    # Versuche Backup-URL, falls vorhanden
    if backup_url:
        print(f"Trying backup URL: {backup_url}")
        try:
            response = requests.get(backup_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(destination, 'wb') as f, tqdm(
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
            print(f"Backup download failed: {e}")
    
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
        
        # Check if file already exists
        if os.path.exists(dest_path):
            # Skip hash check if requested
            if model_info.get("skip_hash_check", False):
                print(f"Model {model_name} already exists (hash check skipped)")
                continue
                
            # Check size and hash
            if "size" in model_info and os.path.getsize(dest_path) == model_info["size"]:
                if "sha256" in model_info and verify_model(dest_path, model_info["sha256"]):
                    print(f"Model {model_name} already exists and is valid")
                    continue
            
            print(f"Existing model {model_name} is invalid, re-downloading")
            os.remove(dest_path)
        
        # Download the model
        print(f"Downloading {model_name} model...")
        download_success = download_file(
            model_info["url"], 
            dest_path, 
            model_info.get("size"),
            backup_url=model_info.get("backup_url")
        )
        
        # Check if download was successful
        if not download_success:
            print(f"Failed to download {model_name} model")
            success = False
            continue
        
        # Verify the hash if needed
        if "sha256" in model_info and not model_info.get("skip_hash_check", False):
            if not verify_model(dest_path, model_info["sha256"]):
                print(f"Verification failed for {model_name} model")
                success = False
                continue
            print(f"Successfully downloaded and verified {model_name} model")
        else:
            print(f"Successfully downloaded {model_name} model (hash check skipped)")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="Download AUTO-TAG models")
    parser.add_argument("--output-dir", default="models", help="Output directory for models")
    args = parser.parse_args()
    
    print("AUTO-TAG Model Downloader")
    print("-----------------------")
    
    if download_models(args.output_dir):
        print("\nAll models downloaded successfully!")
        return 0
    else:
        print("\nSome models failed to download or verify.")
        return 1

if __name__ == "__main__":
    sys.exit(main())