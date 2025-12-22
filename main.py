import argparse
import sys
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

import logging

# Ensure we can import from local package if running from root
sys.path.append(str(Path(__file__).parent.parent))

from stylesync.config import load_config
from stylesync.sync import map_expected_state, clean_output, get_missing_files
from stylesync.clients import get_generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stylesync.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    # Load env vars from the directory this script is in
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    parser = argparse.ArgumentParser(description="StyleSync: Sync images with AI styles.")
    parser.add_argument("--source", required=True, help="Path to source folder containing input images.")
    parser.add_argument("--output", help="Path to output folder. Defaults to ./processed_variants.")
    # Default config relative to this script
    default_config = Path(__file__).parent / "config.yaml"
    parser.add_argument("--config", help=f"Path to config file. Defaults to {default_config.name}", default=str(default_config))
    
    args = parser.parse_args()
    
    # Load Config
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    styles = config.get('styles', [])
    provider = config.get('provider', 'azure')
    
    if not styles:
        print("No styles defined in config.")
        sys.exit(1)
        
    # Initialize Generator
    try:
        generator = get_generator(provider)
        print(f"Using Provider: {provider}")
    except ValueError as e:
        print(f"Error initializing provider: {e}")
        sys.exit(1)
    
    source_dir = Path(args.source)
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)
        
    output_dir = Path(args.output) if args.output else Path("processed_variants")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"--- StyleSync ---")
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print(f"Styles: {len(styles)}")
    
    # Step A: Map Expected State
    print("\nScanning state...")
    expected_state = map_expected_state(source_dir, styles)
    print(f"Expected output files: {len(expected_state)}")
    
    # Step B: Clean Output
    deleted = clean_output(expected_state, output_dir)
    if deleted:
        print(f"Cleaned {len(deleted)} orphaned files.")
        
    # Step C: Generate Missing
    tasks = get_missing_files(expected_state, output_dir)
    print(f"Tasks to process: {len(tasks)}")
    
    if not tasks:
        print("All synchronized. No processing needed.")
        sys.exit(0)
        
    # Process tasks
    print("\nProcessing images...")
    success_count = 0
    fail_count = 0
    
    with tqdm(total=len(tasks)) as pbar:
        for task in tasks:
            source_path = task['source_path']
            style = task['style']
            output_filename = task['output_filename']
            target_path = output_dir / output_filename
            
            pbar.set_description(f"Processing {source_path.name} -> {style['name']}")
            
            # API Call
            result_data = generator.process_image(
                source_path,
                style['prompt_text'],
                style['strength']
            )
            
            if result_data:
                try:
                    with open(target_path, "wb") as f:
                        f.write(result_data)
                    success_count += 1
                except IOError as e:
                    logger.error(f"Error writing file {target_path}: {e}")
                    fail_count += 1
            else:
                logger.warning(f"Failed to generate {output_filename}")
                fail_count += 1
                
            pbar.update(1)
            
    logger.info(f"Completed. Success: {success_count}, Failed: {fail_count}")
    print(f"\nCompleted. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
