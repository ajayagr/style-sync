# StyleSync

StyleSync is a Python application that synchronizes image folders by applying AI-generated style transformations. It supports both **CLI** (local/OneDrive) and **serverless Azure Function** deployments.

## Features

- **Multi-Style Synchronization**: Generate multiple styled versions of each source image.
- **Incremental Updates**: Only processes new/missing images; skips existing outputs.
- **Organized Output**: Outputs stored in style-based subfolders with original copies.
- **Provider Support**:
  - **Azure Foundry**: FLUX.1-Kontext-pro model.
  - **Stability AI**: Stable Diffusion XL model.
- **Storage Support**:
  - **Local**: Standard file system paths (CLI).
  - **OneDrive**: Remote folder syncing (CLI).
  - **Azure Blob Storage**: For serverless function.
- **Cleanup**: Automatically removes orphaned files.
- **Reporting**: Generates detailed Markdown reports (CLI).

## Output Folder Structure

```
target/
├── original/         # Unmodified source copies
├── geometric_3d/     # Style variant 1
├── watercolor/       # Style variant 2
└── ...
```

## Prerequisites

- Python 3.9+
- Active internet connection for API access.

## Installation

```bash
git clone https://github.com/ajayagr/style-sync.git
cd style-sync
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file:

```ini
# Azure Foundry (FLUX.1-Kontext-pro)
AZURE_ENDPOINT_URL=https://<your-endpoint>
AZURE_API_KEY=<your-api-key>

# Stability AI (Alternative)
STABILITY_API_KEY=<your-api-key>

# Azure Blob Storage (for Azure Function)
AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>
CONTAINER_NAME=file-container
```

### Style Configuration

Edit `config.yaml`:

```yaml
provider: azure # Options: azure, stability

styles:
  - index: "01"
    name: "geometric_3d"
    prompt_text: "Turn this into a geometric 3d abstract art piece"
    strength: 0.6

  - index: "02"
    name: "watercolor"
    prompt_text: "Transform into a watercolor painting"
    strength: 0.5
```

## Usage

### CLI - Interactive Mode

```bash
python main.py
```

### CLI - Direct Mode

```bash
python main.py --source "./images" --output "./styled" --config "config.yaml"
```

### Azure Function (Serverless)

**Endpoint:** `POST https://stylesync-function.azurewebsites.net/api/stylesync`

**Request Body:**
```json
{
  "source_folder": "originals/",
  "output_folder": "styled/",
  "container": "file-container",
  "provider": "azure",
  "styles": [
    {"index": "01", "name": "geometric_3d", "prompt_text": "...", "strength": 0.6}
  ]
}
```

## Project Structure

```
stylesync/
├── main.py              # CLI entry point
├── function_app.py      # Azure Function handler
├── sync.py              # Sync logic
├── clients/             # AI provider implementations
├── storage/             # Storage providers (Local, OneDrive, Blob)
├── config.yaml          # Style configuration
├── .github/workflows/   # CI/CD pipeline
└── report/              # Generated execution reports (CLI)
```

## Deployment

The Azure Function auto-deploys via GitHub Actions on push to `main` or `azure-function` branches.

## License

MIT
