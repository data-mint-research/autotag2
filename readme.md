# AUTO-TAG: KI-gestütztes Bild-Tagging System

AUTO-TAG ist ein KI-gestütztes System zur automatischen Analyse von Bildern und Hinzufügung strukturierter Metadaten-Tags. Es verwendet mehrere KI-Modelle, um verschiedene Aspekte von Bildern zu erkennen, einschließlich Szenenklassifikation, Personenerkennung und Kleidungserkennung.

![AUTO-TAG Logo](https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png)

## Funktionen

- **Szenenklassifikation**: Erkennt Innen-/Außenszenen und Raumtypen
- **Personenerkennung**: Zählt Personen und kategorisiert als Solo oder Gruppe
- **Kleidungserkennung**: Klassifiziert den Kleidungsstatus
- **Docker-basiert**: Einfache Einrichtung mit allen Abhängigkeiten in Containern
- **GPU-Beschleunigung**: NVIDIA CUDA-Unterstützung für schnellere Verarbeitung
- **REST API**: Einfache API für die Integration mit anderen Tools
- **Batch-Verarbeitung**: Verarbeitet ganze Ordner mit Statusverfolgung

## Systemanforderungen

- Windows 11 Pro
- Docker Desktop für Windows
- NVIDIA GPU mit CUDA-Unterstützung
- NVIDIA Container Toolkit installiert

## Schnellstart für Einsteiger

### 1. Voraussetzungen installieren

Bevor Sie AUTO-TAG verwenden können, stellen Sie sicher, dass Sie folgende Programme installiert haben:

- [Docker Desktop für Windows](https://www.docker.com/products/docker-desktop)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

Zur vereinfachten Einrichtung des NVIDIA Container Toolkits können Sie unser Setup-Skript verwenden:

```powershell
.\scripts\setup-nvidia-docker.ps1
```

### 2. Repository klonen

Klonen Sie dieses Repository oder laden Sie es herunter:

```powershell
git clone https://github.com/yourusername/auto-tag.git
cd auto-tag
```

### 3. KI-Modelle herunterladen

Vor der ersten Verwendung müssen Sie die KI-Modelle herunterladen:

```powershell
python scripts\download-models.py
```

Dieses Skript lädt alle erforderlichen Modelle in das Verzeichnis `models/` herunter.

### 4. AUTO-TAG starten

Starten Sie AUTO-TAG mit unserem Starter-Skript:

```powershell
.\start.ps1
```

Das Skript startet einen interaktiven Menü-Modus, in dem Sie Bilder oder Ordner verarbeiten können.

## Benutzeroberfläche

Nach dem Start zeigt AUTO-TAG ein einfaches Menü:

```
=====================================
           AUTO-TAG SYSTEM           
             Version 1.0.0     
=====================================

1. Process single image
2. Process folder
3. Check processing status
4. Configure save mode (current: replace)
5. Stop service
6. Exit

Select an option (1-6)
```

### Optionen im Menü

1. **Process single image**: Verarbeitet ein einzelnes Bild (öffnet einen Dateiauswahldialog)
2. **Process folder**: Verarbeitet alle Bilder in einem Ordner
3. **Check processing status**: Zeigt den Fortschritt der Batch-Verarbeitung an
4. **Configure save mode**: Legt fest, ob Originaldateien überschrieben oder neue Dateien erstellt werden
5. **Stop service**: Stoppt den AUTO-TAG-Dienst
6. **Exit**: Beendet das Programm

## Direkte Kommandozeilenbefehle

Sie können AUTO-TAG auch direkt von der Kommandozeile aus verwenden:

```powershell
# Ein einzelnes Bild verarbeiten
.\start.ps1 image C:\pfad\zu\bild.jpg

# Einen Ordner verarbeiten
.\start.ps1 folder C:\pfad\zu\ordner

# Einen Ordner rekursiv verarbeiten
.\start.ps1 folder C:\pfad\zu\ordner -Recursive

# Status prüfen
.\start.ps1 status

# Dienst starten
.\start.ps1 start

# Dienst stoppen
.\start.ps1 stop

# Hilfe anzeigen
.\start.ps1 -Help
```

## Tag-Schema

AUTO-TAG generiert strukturierte Tags in den folgenden Kategorien:

- `scene/indoor|outdoor`: Ob das Bild drinnen oder draußen aufgenommen wurde
- `roomtype/kitchen|bathroom|bedroom|living_room|office`: Art des Raums (für Innenszenen)
- `clothing/dressed|naked`: Kleidungsstatus
- `people/solo|group`: Ob das Bild eine einzelne Person oder mehrere Personen enthält

Diese Tags werden in das XMP-digiKam:TagsList-Feld in den Bild-Metadaten geschrieben, wodurch sie mit Fotoverwaltungsanwendungen wie digiKam, Adobe Lightroom und anderen kompatibel sind.

## API-Nutzung

AUTO-TAG bietet eine REST-API, die Sie für eigene Anwendungen oder Skripte nutzen können:

### Bild verarbeiten

```powershell
# Ein Bild mit curl senden
curl -X POST "http://localhost:8000/process/image" `
    -H "accept: application/json" `
    -H "Content-Type: multipart/form-data" `
    -F "file=@C:\pfad\zu\bild.jpg" `
    -F "tag_mode=append" `
    -F "save_mode=replace"
```

### Ordner verarbeiten

```powershell
# Einen Ordner verarbeiten
curl -X POST "http://localhost:8000/process/folder" `
    -H "accept: application/json" `
    -H "Content-Type: application/json" `
    -d "{ \"path\": \"C:\\pfad\\zu\\ordner\", \"recursive\": false, \"save_mode\": \"replace\" }"
```

### Status abrufen

```powershell
# Verarbeitungsstatus abrufen
curl -X GET "http://localhost:8000/status" -H "accept: application/json"
```

## API-Dokumentation

Eine interaktive API-Dokumentation ist verfügbar, wenn der AUTO-TAG-Dienst läuft:

```
http://localhost:8000/docs
```

Dort können Sie alle API-Endpunkte erkunden und direkt testen.

## Umgebungsvariablen

AUTO-TAG kann über Umgebungsvariablen konfiguriert werden. Fügen Sie diese zu Ihrer `docker-compose.yaml` hinzu oder setzen Sie sie in Ihrer Umgebung:

| Variable | Beschreibung | Standardwert |
|----------|--------------|--------------|
| AUTOTAG_MODELS_DIR | Pfad zum Modellverzeichnis | /app/models |
| AUTOTAG_USE_GPU | GPU-Beschleunigung aktivieren | true |
| AUTOTAG_EXIFTOOL_TIMEOUT | Timeout für ExifTool in Sekunden | 30 |
| AUTOTAG_PORT | API-Port | 8000 |

## Fehlerbehebung

### Häufige Probleme

- **Docker läuft nicht**: Stellen Sie sicher, dass Docker Desktop ausgeführt wird
- **GPU wird nicht erkannt**: Überprüfen Sie, ob das NVIDIA Container Toolkit richtig konfiguriert ist
- **Dienst startet nicht**: Überprüfen Sie die Docker-Logs mit `docker-compose logs`
- **Langsame Verarbeitung**: Prüfen Sie, ob die GPU-Beschleunigung funktioniert

### Logs überprüfen

Um die Logs des AUTO-TAG-Dienstes anzuzeigen:

```powershell
docker-compose logs -f
```

Detailliertere Logs finden Sie im `logs`-Verzeichnis.

## Erweiterte Konfiguration

Für fortgeschrittene Benutzer bietet AUTO-TAG verschiedene Konfigurationsmöglichkeiten:

### Konfigurationsdatei

Sie können die `config.yml` Datei bearbeiten, um das Verhalten von AUTO-TAG anzupassen:

```yaml
# Hardware-Einstellungen
hardware:
  use_gpu: true
  cuda_device_id: 0

# Modell-Einstellungen
models:
  clip:
    path: '/app/models/clip/clip_vit_b32.pth'
    architecture: 'ViT-B-32'
  yolo:
    path: '/app/models/yolov8/yolov8n.pt'
    min_person_height: 40

# Tagging-Einstellungen
tagging:
  mode: 'append'
  min_confidence_percent: 80
  exiftool_timeout: 30
```

### Docker-Konfiguration

Sie können die `docker-compose.yaml` Datei anpassen, um die Container-Konfiguration zu ändern:

```yaml
version: '3.8'

services:
  autotag:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - CUDA_VISIBLE_DEVICES=0
      - AUTOTAG_MODELS_DIR=/app/models
      - AUTOTAG_USE_GPU=true
      - AUTOTAG_EXIFTOOL_TIMEOUT=30
    volumes:
      - ./config.yml:/app/config.yml
      - ./logs:/app/logs
```

## Lizenz

MIT-Lizenz

## Danksagungen

- [CLIP](https://github.com/openai/CLIP) für die Szenenklassifikation
- [YOLOv8](https://github.com/ultralytics/ultralytics) für die Objekterkennung
- [ExifTool](https://exiftool.org/) für die Metadatenverwaltung