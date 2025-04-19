import os
import torch
from PIL import Image
import numpy as np
from typing import Dict, Tuple, Optional
import logging

# Konfiguration laden
from config import get_config

logger = logging.getLogger('auto-tag')

# Predefined categories for classification
SCENE_CATEGORIES = ["indoor", "outdoor"]
ROOMTYPES = ["kitchen", "bathroom", "bedroom", "living room", "office"]
CLOTHING = ["dressed", "naked"]

class CLIPModel:
    """CLIP model for scene and clothing classification"""
    
    def __init__(self):
        """Initialize CLIP model"""
        config = get_config()
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.device = "cuda" if config["hardware"]["use_gpu"] and torch.cuda.is_available() else "cpu"
        self.model_path = config["models"]["clip"]["path"]
        self.model_architecture = config["models"]["clip"]["architecture"]
        self.initialized = False
    
    def initialize(self):
        """Initialize the model"""
        if self.initialized:
            return True
        
        try:
            # Import CLIP
            import open_clip
            
            # Load model and transformer
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_architecture,
                pretrained=False
            )
            
            # Manuelles Laden der Modellgewichte
            logger.info(f"Lade CLIP-Modell aus: {self.model_path}")
            state_dict = torch.load(self.model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            
            self.model = self.model.to(self.device).eval()
            
            # Load tokenizer
            self.tokenizer = open_clip.get_tokenizer(self.model_architecture)
            
            self.initialized = True
            logger.info(f"CLIP model successfully initialized on {self.device}")
            return True
        except Exception as e:
            logger.error(f"Error initializing CLIP model: {e}", exc_info=True)
            return False
    
    def analyze(self, image_path: str) -> Dict[str, Tuple[str, float]]:
        """Analyze scene and clothing with CLIP"""
        # Initialize model if needed
        if not self.initialized:
            if not self.initialize():
                return {}
        
        try:
            # Load and prepare image with proper resource management
            with Image.open(image_path) as image:
                image_rgb = image.convert("RGB")
                image_tensor = self.preprocess(image_rgb).unsqueeze(0).to(self.device)
                
                # Classify scene, room type, and clothing
                scene = self._classify(image_tensor, SCENE_CATEGORIES)[0]
                room = self._classify(image_tensor, ROOMTYPES)[0]
                clothing = self._classify(image_tensor, CLOTHING)[0]
            
            return {
                "scene": scene,
                "roomtype": room,
                "clothing": clothing
            }
        except Exception as e:
            logger.error(f"Error analyzing image: {e}", exc_info=True)
            return {}
    
    def _classify(self, image_tensor, label_list, topk=1):
        """Classify image against text prompts"""
        with torch.no_grad():
            # Create text prompts
            text_inputs = self.tokenizer([f"a photo of {label}" for label in label_list]).to(self.device)
            
            # Encode image and text
            image_features = self.model.encode_image(image_tensor)
            text_features = self.model.encode_text(text_inputs)
            
            # Normalize features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            # Calculate similarity
            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            probs = similarity.squeeze().cpu().numpy()
            
            # Sort by probability
            results = list(zip(label_list, probs))
            sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
            
            return sorted_results[:topk]

class YOLOModel:
    """YOLOv8 model for person detection and counting"""
    
    def __init__(self):
        """Initialize YOLOv8 model"""
        config = get_config()
        self.model = None
        self.device = "cuda" if config["hardware"]["use_gpu"] and torch.cuda.is_available() else "cpu"
        self.model_path = config["models"]["yolo"]["path"]
        self.initialized = False
        self.min_person_height = config["models"]["yolo"]["min_person_height"]
    
    def initialize(self):
        """Initialize the model"""
        if self.initialized:
            return True
        
        try:
            # Import YOLO
            from ultralytics import YOLO
            
            # Load model
            self.model = YOLO(self.model_path)
            
            self.initialized = True
            logger.info(f"YOLOv8 model successfully initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing YOLOv8 model: {e}", exc_info=True)
            return False
    
    def count_people(self, image_path: str) -> str:
        """Count people in the image"""
        # Initialize model if needed
        if not self.initialized:
            if not self.initialize():
                return "none"
        
        try:
            # Run inference
            results = self.model(image_path)
            
            # Count people (class 0 in COCO)
            count = 0
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    cls = int(box.cls[0].item())
                    if cls == 0:  # Person
                        height = int(box.xywh[0][3].item())  # Box height
                        if height >= self.min_person_height:
                            count += 1
            
            # Categorize the result
            if count == 0:
                return "none"
            elif count == 1:
                return "solo"
            else:
                return "group"
                
        except Exception as e:
            logger.error(f"Error counting people in {image_path}: {e}", exc_info=True)
            return "none"

# Singleton instances
_clip_model = None
_yolo_model = None

def get_clip_model():
    """Get or initialize CLIP model singleton"""
    global _clip_model
    if _clip_model is None:
        _clip_model = CLIPModel()
        _clip_model.initialize()
    return _clip_model

def get_yolo_model():
    """Get or initialize YOLOv8 model singleton"""
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLOModel()
        _yolo_model.initialize()
    return _yolo_model