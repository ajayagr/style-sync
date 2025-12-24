# StyleSync

StyleSync is a Python CLI application that synchronizes image folders by applying AI-generated style transformations. It processes images from a source directory (Local or OneDrive) and generates styled variants in an output directory using Azure Foundry (FLUX.1-Kontext-pro) or Stability AI.

## Features

- **Multi-Style Synchronization**: Automatically generates multiple styled versions of each source image based on configuration.
- **Incremental Updates**: Only processes new or modified images; skips existing valid outputs.
- **Provider Support**:
  - **Azure Foundry**: FLUX.1-Kontext-pro model.
  - **Stability AI**: Stable Diffusion XL model.
- **Storage Support**:
  - **Local**: Standard file system paths.
  - **OneDrive**: Remote folder syncing (requires authentication).
- **Cleanup**: Automatically removes orphaned files that no longer match the current configuration.
- **Reporting**: Generates a detailed Markdown report after each run.

## Prerequisites

- Python 3.8+
- Active internet connection for API access.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd stylesync
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: if requirements.txt is mapped, otherwise install: `pip install tqdm python-dotenv requests`)*

## Configuration

### Environment Variables
Create a `.env` file in the root directory:

```ini
# Azure Foundry (FLUX.1-Kontext-pro)
AZURE_ENDPOINT_URL=https://<your-endpoint>
AZURE_API_KEY=<your-api-key>

# Stability AI (Alternative)
STABILITY_API_KEY=<your-api-key>

# OneDrive (If using OneDrive storage)
ONEDRIVE_ACCESS_TOKEN=<your-access-token>
# Optional: ONEDRIVE_CLIENT_ID=<client-id>
```

### Style Configuration
Edit `config.yaml` to define your styles and provider:

```yaml
provider: azure # Options: azure, stability

styles:
  - index: "01"
    name: "geometric_3d"
    prompt_text: "Turn this into a geometric 3d abstract art piece, low poly, vibrant colors"
    strength: 0.6

  - index: "02"
    name: "anime"
    prompt_text: "Transform this image into anime style, cel shaded"
    strength: 0.5
```

## Usage

### Interactive Mode
Run without arguments to start the interactive wizard for selecting Local/OneDrive paths.
```bash
python main.py
```

### CLI Mode (Local Only)
Specify source, output, and config paths directly.
```bash
python main.py --source "./input_images" --output "./output_images" --config "config.yaml"
```

## Directory Structure

- `main.py`: Entry point.
- `stylesync/`: Core logic package.
- `clients/`: AI provider implementations.
- `config.yaml`: Configuration file.
- `report/`: Generated execution reports.

## License
MIT
