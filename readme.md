# AUTO-TAG: Docker-Based Image Tagging System

AUTO-TAG is an AI-powered image tagging system that automatically analyzes images and adds structured metadata tags. It uses multiple AI models to detect various aspects of images, including scene classification, person detection, and clothing detection.

## Features

- **Scene Classification**: Identifies indoor/outdoor scenes and room types
- **Person Detection**: Counts people and categorizes as solo or group
- **Clothing Detection**: Classifies clothing status
- **Docker-Based**: Easy setup with all dependencies containerized
- **GPU Acceleration**: NVIDIA CUDA support for faster processing
- **REST API**: Simple API for integration with other tools
- **Batch Processing**: Process entire folders with status tracking

## Requirements

- Windows 11 Pro
- Docker Desktop for Windows
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit installed

## How It Works

This Docker-based implementation offers a streamlined approach to automatic image tagging with AI:

- The system uses Docker to create a consistent environment with all dependencies
- NVIDIA GPU acceleration is automatically leveraged when available
- AI models (CLIP, YOLOv8) analyze images for scene content, people, and clothing
- ExifTool writes structured tags to the image metadata
- All processing happens within the container, keeping your system clean

### Key Benefits:

- **No Python dependencies** to manage on your host system
- **Consistent environment** across different machines
- **Simple user interface** through PowerShell
- **Pre-downloaded models** avoid internet dependency during operation
- **Structured tags** compatible with photo management software

## Quick Start

1. Clone this repository
2. Download the models (one-time setup):
   ```
   python download_models.py
   ```
3. Run the start script:
   ```
   .\start.ps1
   ```
4. Use the interactive menu to process images or folders

## First-Time Setup

Before using AUTO-TAG, make sure you have:

1. **Docker Desktop for Windows** installed with NVIDIA Container Toolkit configured
2. Created the required directories:
   ```
   mkdir -p data/input data/output
   ```
3. Downloaded the AI models:
   ```
   python download_models.py
   ```

## Directory Structure

```
AUTO-TAG/
├── app/                  # Application code
│   ├── main.py           # Main entry point
│   ├── models.py         # AI models
│   ├── tagger.py         # Image tagging
│   └── utils.py          # Utility functions
├── models/               # Pre-downloaded models
│   ├── clip/
│   ├── yolov8/
│   └── facenet/
├── data/                 # Data directories
│   ├── input/            # Input images
│   └── output/           # Output images
├── Dockerfile            # Docker container definition
├── docker-compose.yml    # Container orchestration
├── config.yml            # Configuration file
├── requirements.txt      # Python dependencies
├── download_models.py    # Model downloader
├── start.ps1             # PowerShell startup script
└── README.md             # This file
```

## Command Line Usage

```powershell
# Process a single image
.\start.ps1 image C:\path\to\image.jpg

# Process a folder
.\start.ps1 folder C:\path\to\folder

# Process a folder recursively
.\start.ps1 folder C:\path\to\folder -Recursive

# Check processing status
.\start.ps1 status

# Start the service
.\start.ps1 start

# Stop the service
.\start.ps1 stop

# Show help
.\start.ps1 -Help
```

## Tag Schema

AUTO-TAG generates structured tags in the following categories:

- `scene/indoor|outdoor`: Whether the image is indoor or outdoor
- `roomtype/kitchen|bathroom|bedroom|living_room|office`: Type of room (for indoor scenes)
- `clothing/dressed|naked`: Clothing status
- `people/solo|group`: Whether the image contains a single person or multiple people

These tags are written to the XMP-digiKam:TagsList field in the image metadata, making them compatible with photo management applications like digiKam, Adobe Lightroom, and others.

## Docker Setup

Make sure you have Docker Desktop for Windows installed with the NVIDIA Container Toolkit configured. The application uses a containerized approach for easy setup and deployment.

To verify that NVIDIA Docker support is working:
```powershell
docker run --rm --gpus all nvidia/cuda:12.0.1-base-ubuntu22.04 nvidia-smi
```

You should see the output of `nvidia-smi` showing your GPU information.

## API Endpoints

AUTO-TAG exposes a REST API that can be used by other applications:

- `POST /process/image` - Process a single image (multipart/form-data)
- `POST /process/folder` - Process a folder of images
- `GET /status` - Get the current processing status

## Customizing Configuration

Edit the `config.yml` file to customize the behavior of AUTO-TAG:

- Change the paths for input and output directories
- Adjust the minimum confidence threshold
- Configure model-specific settings

## Troubleshooting

### Common Issues

- **Docker not running**: Make sure Docker Desktop is running
- **GPU not detected**: Verify NVIDIA Container Toolkit is properly configured
- **Service won't start**: Check Docker logs with `docker-compose logs`
- **Slow processing**: Check that GPU acceleration is working

### Checking Logs

To view the logs from the AUTO-TAG service:
```powershell
docker-compose logs -f
```

## License

MIT License

## Acknowledgments

- [CLIP](https://github.com/openai/CLIP) for scene classification
- [YOLOv8](https://github.com/ultralytics/ultralytics) for object detection
- [ExifTool](https://exiftool.org/) for metadata handling