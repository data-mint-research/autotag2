import os
import yaml
from typing import Dict, Any

# Standardkonfiguration
DEFAULT_CONFIG = {
    "paths": {
        "models_dir": "/app/models"
    },
    "hardware": {
        "use_gpu": True,
        "cuda_device_id": 0
    },
    "models": {
        "clip": {
            "path": "{paths.models_dir}/clip/clip_vit_b32.pth",
            "architecture": "ViT-B-32"
        },
        "yolo": {
            "path": "{paths.models_dir}/yolov8/yolov8n.pt",
            "min_person_height": 40
        },
        "facenet": {
            "path": "{paths.models_dir}/facenet/facenet_model.pth"
        }
    },
    "tagging": {
        "mode": "append",
        "min_confidence_percent": 80,
        "exiftool_timeout": 30
    },
    "api": {
        "port": 8000,
        "host": "0.0.0.0"
    }
}

# Umgebungsvariablen-Mapping (mit Namenskonvention)
ENV_MAPPING = {
    "AUTOTAG_MODELS_DIR": "paths.models_dir",
    "AUTOTAG_USE_GPU": "hardware.use_gpu",
    "AUTOTAG_CUDA_DEVICE": "hardware.cuda_device_id",
    "AUTOTAG_PORT": "api.port",
    "AUTOTAG_HOST": "api.host",
    "AUTOTAG_TAG_MODE": "tagging.mode",
    "AUTOTAG_MIN_CONFIDENCE": "tagging.min_confidence_percent",
    "AUTOTAG_EXIFTOOL_TIMEOUT": "tagging.exiftool_timeout"
}

def _set_nested_value(config: Dict[str, Any], key_path: str, value: Any) -> None:
    """Setzt einen verschachtelten Wert in der Konfiguration basierend auf einem Pfad."""
    keys = key_path.split('.')
    current = config
    
    # Navigiere zur letzten Ebene
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
        
    # Setze den Wert
    final_key = keys[-1]
    
    # Typumwandlung basierend auf Standardtyp
    path_value = DEFAULT_CONFIG
    for k in keys[:-1]:
        path_value = path_value.get(k, {})
    
    default_value = path_value.get(final_key)
    if isinstance(default_value, bool):
        if isinstance(value, str):
            value = value.lower() in ('true', 'yes', '1', 'y')
    elif isinstance(default_value, int):
        try:
            value = int(value)
        except ValueError:
            pass
    
    current[final_key] = value

def _resolve_template_strings(config: Dict[str, Any]) -> Dict[str, Any]:
    """Löst Template-Strings in der Konfiguration auf."""
    config_str = str(config)
    
    # Ersetze alle Template-Strings
    changed = True
    while changed:
        new_config_str = config_str
        
        # Ersetze {key} mit dem tatsächlichen Wert
        for key, value in _flatten_dict(config).items():
            if isinstance(value, str):
                placeholder = "{" + key + "}"
                new_config_str = new_config_str.replace(placeholder, str(value))
        
        changed = new_config_str != config_str
        config_str = new_config_str
    
    # Konvertiere zurück zu Dictionary
    import ast
    return ast.literal_eval(config_str)

def _flatten_dict(d: Dict[str, Any], parent_key: str = '') -> Dict[str, Any]:
    """Flacht ein verschachteltes Dictionary ab."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)

def load_config(config_path: str = 'config.yml') -> Dict[str, Any]:
    """
    Lädt die Konfiguration mit folgender Priorität:
    1. Umgebungsvariablen
    2. Konfigurationsdatei
    3. Standardwerte
    """
    # Starte mit Standardkonfiguration
    config = DEFAULT_CONFIG.copy()
    
    # Lade aus Konfigurationsdatei
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = yaml.safe_load(f) or {}
                
                # Rekursives Update der Konfiguration
                def update_recursive(d, u):
                    for k, v in u.items():
                        if isinstance(v, dict):
                            d[k] = update_recursive(d.get(k, {}), v)
                        else:
                            d[k] = v
                    return d
                
                config = update_recursive(config, file_config)
        except Exception as e:
            print(f"Warnung: Fehler beim Laden der Konfigurationsdatei: {e}")
    
    # Überschreibe mit Umgebungsvariablen
    for env_var, config_path in ENV_MAPPING.items():
        if env_var in os.environ:
            _set_nested_value(config, config_path, os.environ[env_var])
    
    # Löse Template-Strings auf
    config = _resolve_template_strings(config)
    
    return config

# Singleton-Instanz der Konfiguration
_config = None

def get_config() -> Dict[str, Any]:
    """Gibt die Konfiguration zurück (Singleton-Muster)"""
    global _config
    if _config is None:
        _config = load_config()
    return _config