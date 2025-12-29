# StyleSync Serverless

A serverless Azure Function that applies AI style transformations to images stored in Azure Blob Storage.

## Features

- **HTTP Triggered** - Call on-demand via REST API
- **Azure Blob Storage** - Reads from source folder, writes to styled output folders
- **Multiple Styles** - Apply multiple AI styles in a single request
- **Incremental Processing** - Skips already-processed images
- **Original Copies** - Automatically copies originals to `original/` folder

## Output Structure

```
styled/
├── original/         # Unmodified source copies
├── geometric_3d/     # Style variant 1
├── watercolor/       # Style variant 2
└── ...
```

## Deployment

### Prerequisites
- Azure Function App (Python 3.11, Linux, Consumption Plan)
- Azure Storage Account with container

### Required App Settings
Configure these in Azure Portal → Function App → Configuration:

| Setting | Description |
|---------|-------------|
| `AZURE_STORAGE_CONNECTION_STRING` | Storage account connection string |
| `AZURE_API_KEY` | AI API key for image processing |
| `AZURE_ENDPOINT_URL` | AI endpoint URL |
| `CONTAINER_NAME` | Default container name (optional) |
| `AzureWebJobsFeatureFlags` | Set to `EnableWorkerIndexing` |

### Deploy via GitHub Actions
Push to `serverless` branch triggers automatic deployment.

## API Usage

**Endpoint:** `POST https://<function-app>.azurewebsites.net/api/stylesync`

**Request Body:**
```json
{
    "source_folder": "originals/",
    "output_folder": "styled/",
    "container": "file-container",
    "styles": [
        {
            "name": "geometric_3d",
            "prompt_text": "Turn this into geometric 3D abstract art, low poly, vibrant colors"
        },
        {
            "name": "watercolor",
            "prompt_text": "Transform into a beautiful watercolor painting"
        }
    ]
}
```

**Response:**
```json
{
    "status": "completed",
    "source": "file-container/originals/",
    "output": "file-container/styled/",
    "processed": ["geometric_3d/image1.jpg", "watercolor/image1.jpg"],
    "copied": ["original/image1.jpg"],
    "failed": [],
    "skipped": []
}
```

## Project Structure

```
stylesync/
├── StyleSyncFunction/
│   ├── __init__.py       # Function handler
│   └── function.json     # HTTP trigger binding
├── host.json             # Function app settings
├── requirements.txt      # Python dependencies
└── .github/workflows/    # CI/CD pipeline
```

## Local Development

```bash
# Install Azure Functions Core Tools
npm install -g azure-functions-core-tools@4

# Install dependencies
pip install -r requirements.txt

# Run locally
func start
```

## License
MIT
