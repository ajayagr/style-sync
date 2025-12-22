# StyleSync

StyleSync is a powerful CLI tool for automating bulk image restyling using state-of-the-art AI models (Black Forest Labs Flux via Azure, or Stability AI). It treats style variants as a synchronization problem—ensuring your output folder always matches your source images plus your defined style configuration.

## Features

- **Smart Synchronization**: Only generates images that are missing. If you add new source images or new styles, it processes only the deltas.
- **Bulk Processing**: seamlessly handles entire directories of input images.
- **Orphan Cleanup**: If you remove a style from the config or delete a source image, the corresponding output variants are automatically cleaned up.
- **Multi-Provider Support**: 
  - **Azure**: Uses BFL Flux.1-Kontext-Pro (optimized for image-to-image).
  - **Stability AI**: Uses Stable Diffusion XL.
- **Configurable Styles**: Define prompts, strength, and naming conventions in a simple YAML file.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd stylesync
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the `stylesync` directory (or root) with your API keys:
   ```ini
   # For Azure (BFL Flux)
   AZURE_API_KEY=your_azure_key
   AZURE_ENDPOINT_URL=https://<your-resource>.services.ai.azure.com/...

   # For Stability AI
   STABILITY_API_KEY=your_stability_key
   ```

## Configuration

Edit `stylesync/config.yaml` to define your target styles.

```yaml
provider: azure  # or 'stability'

styles:
  - name: anime
    index: 01
    prompt_text: "anime style, vibrant colors, cel shaded"
    strength: 0.75

  - name: sketch
    index: 02
    prompt_text: "pencil sketch, black and white, rough lines"
    strength: 0.60
```

*   **name**: Used for logging and identifying the style.
*   **index**: Suffix added to the filename (e.g., `image_01.png`).
*   **strength**: How much to change the image (0.0 to 1.0). Higher = more AI influence.

## Usage

Run the CLI by specifying your source folder.

```bash
# Basic usage (Output defaults to ./processed_variants)
python stylesync/main.py --source ./input_images

# Specify output folder
python stylesync/main.py --source ./input_images --output ./my_output

# Use a specific config file
python stylesync/main.py --source ./input_images --config ./my_config.yaml
```

## Project Structure

*   `stylesync/main.py`: Entry point for the CLI.
*   `stylesync/sync.py`: Core logic for mapping expected files and detecting changes.
*   `stylesync/clients/`: API client implementations (Azure, Stability).
*   `stylesync/config.yaml`: Default configuration.
