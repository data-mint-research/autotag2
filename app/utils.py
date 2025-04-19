import os
import torch
import yaml
import logging
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Any
from logging.handlers import RotatingFileHandler

# Konfiguration laden
from config import get_config

# Logging einrichten
def setup_logging(log_dir="logs", log_level=logging.INFO):
    """Konfiguriert das Logging-System mit rotierenden Dateien"""
    
    # Logverzeichnis erstellen, falls nicht vorhanden
    os.makedirs(log_dir, exist_ok=True)
    
    # Formatter für strukturierte Logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    
    # Handler für rotierende Logdateien (max. 5MB pro Datei, max. 5 Dateien)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'auto-tag.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Handler für Konsole
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Root-Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Hauptlogger für die Anwendung
    logger = logging.getLogger('auto-tag')
    logger.info("Logging system initialized")
    
    return logger

# Konfiguriere den Logger
logger = setup_logging()

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
    "save_mode": "replace",
    "progress_percent": 0,
    "phase": "",
    "recent_status": [],
    "errors": [],
    "stats": {
        "avg_time_per_image": 0,
        "fastest_image": {"file": "", "time": float('inf')},
        "slowest_image": {"file": "", "time": 0}
    }
}
_status_lock = threading.Lock()

def setup_environment():
    """Set up the environment for processing"""
    config = get_config()
    
    # Optimize CUDA if available
    if torch.cuda.is_available() and config["hardware"]["use_gpu"]:
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
        logger.warning("CUDA is not available or disabled, using CPU mode")

def find_images(folder_path: str, recursive: bool = False) -> List[str]:
    """Find all images in a folder"""
    if not os.path.exists(folder_path):
        logger.error(f"Folder not found: {folder_path}")
        return []
    
    # Unterstützte Bildformate
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
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

def _update_status_phase(phase: str, message: str):
    """Aktualisiert die aktuelle Phase und Nachricht"""
    with _status_lock:
        _processing_status["phase"] = phase
        _add_status_message("system", message)
        logger.info(message)

def _update_status_current(current: int, total: int, filename: str):
    """Aktualisiert den aktuellen Verarbeitungsstatus"""
    with _status_lock:
        _processing_status["current_file"] = filename
        _processing_status["progress_percent"] = round((current / total) * 100, 1) if total > 0 else 0

def _add_status_message(file: str, message: str):
    """Fügt eine Statusmeldung zur Historie hinzu"""
    with _status_lock:
        # Begrenze die Liste auf die letzten 10 Einträge
        if len(_processing_status["recent_status"]) >= 10:
            _processing_status["recent_status"].pop(0)
        
        _processing_status["recent_status"].append({
            "time": time.time(),
            "file": file,
            "message": message
        })

def _add_error(file: str, message: str):
    """Fügt eine Fehlermeldung zur Liste hinzu"""
    with _status_lock:
        _processing_status["errors"].append({
            "time": time.time(),
            "file": file,
            "message": message
        })

def _update_eta(processed: int, total: int, total_time: float):
    """Aktualisiert die geschätzte verbleibende Zeit"""
    with _status_lock:
        if processed > 0:
            time_per_file = total_time / processed
            remaining_files = total - processed
            _processing_status["eta_seconds"] = time_per_file * remaining_files

def batch_process_folder(folder_path: str, recursive: bool = False, save_mode: str = "replace"):
    """
    Process all images in a folder with erweiterten Statusberichten
    
    Args:
        folder_path: Path to the folder containing images
        recursive: Whether to process subfolders recursively
        save_mode: How to save the tagged files - "replace" (overwrite originals) or "suffix" (create new files)
    """
    global _processing_status
    
    # Erweiterten Status initialisieren
    with _status_lock:
        _processing_status.update({
            "active": True,
            "current_path": folder_path,
            "total_files": 0,
            "processed_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "start_time": time.time(),
            "current_file": "",
            "eta_seconds": 0,
            "save_mode": save_mode,
            "output_files": [],
            # Status zurücksetzen
            "progress_percent": 0,
            "phase": "scanning",
            "recent_status": [],
            "errors": [],
            "stats": {
                "avg_time_per_image": 0,
                "fastest_image": {"file": "", "time": float('inf')},
                "slowest_image": {"file": "", "time": 0}
            }
        })
    
    try:
        # Phase: Scanning
        _update_status_phase("scanning", f"Suche Bilder in {folder_path}")
        
        # Finde alle Bilder
        image_files = find_images(folder_path, recursive)
        
        with _status_lock:
            _processing_status["total_files"] = len(image_files)
        
        if not image_files:
            _update_status_phase("complete", f"Keine Bilder in {folder_path} gefunden")
            with _status_lock:
                _processing_status["active"] = False
            return
        
        # Phase: Processing
        _update_status_phase("processing", f"Verarbeite {len(image_files)} Bilder")
        
        # Modifizierte Bildverarbeitung mit detailliertem Status
        from tagger import process_image, write_tags_to_file
        
        total_processing_time = 0
        
        for index, image_file in enumerate(image_files):
            file_basename = os.path.basename(image_file)
            
            # Status aktualisieren
            _update_status_current(index, len(image_files), file_basename)
            
            # Bild verarbeiten
            start_time = time.time()
            result = process_image(image_file)
            processing_time = time.time() - start_time
            
            # Verarbeitungszeit verfolgen
            total_processing_time += processing_time
            
            # Status-Update für das aktuelle Bild
            with _status_lock:
                avg_time = total_processing_time / (index + 1)
                _processing_status["stats"]["avg_time_per_image"] = avg_time
                
                # Schnellstes/langsamsten Bild aktualisieren
                if processing_time < _processing_status["stats"]["fastest_image"]["time"]:
                    _processing_status["stats"]["fastest_image"] = {
                        "file": file_basename,
                        "time": processing_time
                    }
                
                if processing_time > _processing_status["stats"]["slowest_image"]["time"]:
                    _processing_status["stats"]["slowest_image"] = {
                        "file": file_basename,
                        "time": processing_time
                    }
            
            # Tags schreiben, wenn erfolgreich
            status_message = ""
            if result["success"]:
                tags = result["tags"]
                tag_success, output_path = write_tags_to_file(image_file, tags, save_mode=save_mode)
                
                with _status_lock:
                    _processing_status["processed_files"] += 1
                    if tag_success:
                        _processing_status["successful_files"] += 1
                        _processing_status["output_files"].append(output_path)
                        status_message = f"Erfolgreich: {len(tags)} Tags hinzugefügt ({processing_time:.2f}s)"
                    else:
                        _processing_status["failed_files"] += 1
                        status_message = f"Fehler beim Schreiben der Tags ({processing_time:.2f}s)"
                        _add_error(file_basename, "Fehler beim Schreiben der Tags")
            else:
                with _status_lock:
                    _processing_status["processed_files"] += 1
                    _processing_status["failed_files"] += 1
                    error_msg = result.get("error", "Unbekannter Fehler")
                    status_message = f"Fehler: {error_msg} ({processing_time:.2f}s)"
                    _add_error(file_basename, error_msg)
            
            # Letzten Status hinzufügen
            _add_status_message(file_basename, status_message)
            
            # ETA aktualisieren
            _update_eta(index + 1, len(image_files), total_processing_time)
        
        # Phase: Complete
        completion_message = f"Verarbeitung abgeschlossen: {_processing_status['successful_files']}/{_processing_status['total_files']} erfolgreich"
        _update_status_phase("complete", completion_message)
        
        # Finales Status-Update
        with _status_lock:
            _processing_status["active"] = False
            _processing_status["progress_percent"] = 100
            _processing_status["current_file"] = ""
            
        logger.info(completion_message)
        
    except Exception as e:
        logger.error(f"Fehler bei der Batch-Verarbeitung: {e}", exc_info=True)
        _update_status_phase("error", f"Verarbeitung fehlgeschlagen: {str(e)}")
        with _status_lock:
            _processing_status["active"] = False

def get_processing_status():
    """Get the current processing status"""
    with _status_lock:
        status = _processing_status.copy()
        
        # Menschenlesbare Formatierung hinzufügen
        if status["active"]:
            # ETA formatieren
            if status["eta_seconds"] > 0:
                eta = status["eta_seconds"]
                hours, remainder = divmod(eta, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    status["eta_formatted"] = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                else:
                    status["eta_formatted"] = f"{int(minutes)}m {int(seconds)}s"
            
            # Laufzeit formatieren
            runtime = time.time() - status["start_time"]
            hours, remainder = divmod(runtime, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                status["runtime_formatted"] = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            else:
                status["runtime_formatted"] = f"{int(minutes)}m {int(seconds)}s"
                
        return status

# Funktion zum Erstellen temporärer Dateien mit Tracking-Präfix
def create_temp_file(prefix="autotag_", suffix=None):
    """Erstellt eine temporäre Datei mit Tracking-Präfix"""
    import tempfile
    return tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix, delete=False)

# Bereinigungsfunktion
def cleanup_resources():
    """Räumt alle Ressourcen vor dem Beenden der Anwendung auf"""
    logger.info("Bereinige Ressourcen...")
    
    # GPU-Speicher freigeben
    if torch.cuda.is_available():
        logger.info("Gebe GPU-Speicher frei...")
        torch.cuda.empty_cache()
    
    # Temporäre Dateien bereinigen
    import tempfile
    import glob
    
    temp_pattern = os.path.join(tempfile.gettempdir(), "autotag_*")
    temp_files = glob.glob(temp_pattern)
    logger.info(f"Lösche {len(temp_files)} temporäre Dateien...")
    
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Konnte temporäre Datei nicht löschen: {temp_file} - {e}")
    
    logger.info("Ressourcenbereinigung abgeschlossen.")