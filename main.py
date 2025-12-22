import argparse
import sys
import os
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv
import logging
import io

# Ensure we can import from local package if running from root
sys.path.append(str(Path(__file__).parent.parent))

from stylesync.config import load_config
from stylesync.sync import map_expected_state, clean_output, get_missing_files
from stylesync.clients import get_generator
from stylesync.storage import LocalStorageProvider, OneDriveStorageProvider
from stylesync.storage.auth import get_onedrive_token

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

def select_provider(name: str, existing_token: str = None):
    print(f"\nSelect {name} Storage Type:")
    print("1. Local")
    print("2. OneDrive (Requires ONEDRIVE_ACCESS_TOKEN in .env)")
    
    while True:
        choice = input("Enter choice [1/2]: ").strip()
        if choice == "1":
            path = input(f"Enter Local {name} Path: ").strip()
            return LocalStorageProvider(), path, existing_token
        elif choice == "2":
            if existing_token:
                token = existing_token
            else:
                # Try to get Client ID from env (optional customization), else use default in auth module
                client_id = os.environ.get("ONEDRIVE_CLIENT_ID")
                # Initiate Authentication Flow
                token = get_onedrive_token(client_id)
            
            if not token:
                print("Authentication failed or cancelled.")
                continue
                
            path = input(f"Enter OneDrive {name} Path (relative to root): ").strip()
            return OneDriveStorageProvider(token), path, token
        else:
            print("Invalid choice.")

def main():
    # Load env vars from the directory this script is in
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    parser = argparse.ArgumentParser(description="StyleSync v1.0: Sync images with AI styles.")
    parser.add_argument("--source", help="Path to source folder (Local). Use interactive mode for Remote.")
    parser.add_argument("--output", help="Path to output folder (Local). Use interactive mode for Remote.")
    
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
    provider_name = config.get('provider', 'azure')
    
    print(f"--- StyleSync v1.0 ({provider_name}) ---")

    # Determine Storage Providers
    if args.source and args.output:
        # Command line args imply local storage compatibility for now, 
        # or we could parse "onedrive://path" later. For now, CLI args = Local.
        source_provider = LocalStorageProvider()
        source_path = args.source
        
        output_provider = LocalStorageProvider()
        output_path = args.output
    else:
        # Interactive Mode
        current_token = None
        
        source_provider, source_path, current_token = select_provider("Source", current_token)
        output_provider, output_path, current_token = select_provider("Output", current_token)

    # Initialize Generator
    try:
        generator = get_generator(provider_name)
    except ValueError as e:
        print(f"Error initializing provider: {e}")
        sys.exit(1)
    
    # Ensure Output exists
    output_provider.mkdir(output_path)

    print(f"\nSource: {source_path} ({type(source_provider).__name__})")
    print(f"Output: {output_path} ({type(output_provider).__name__})")
    print(f"Styles: {len(styles)}")
    
    # Step A: Map Expected State
    print("\nScanning state...")
    try:
        expected_state = map_expected_state(source_provider, source_path, styles)
        print(f"Expected output files: {len(expected_state)}")
        
        # Step B: Clean Output
        deleted = clean_output(output_provider, expected_state, output_path)
        if deleted:
            print(f"Cleaned {len(deleted)} orphaned files.")
            
        # Step C: Generate Missing
        tasks = get_missing_files(output_provider, expected_state, output_path)
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
                source_item = task['source_item']
                style = task['style']
                output_filename = task['output_filename']
                
                # Full paths for logging/display, though providers use specific logic
                display_name = source_item.name
                
                pbar.set_description(f"Processing {display_name} -> {style['name']}")
                
                try:
                    # READ Source
                    input_data = source_provider.read_file(source_item.path)
                    
                    # We need a temporary file path for the 'client' because currently
                    # clients expect a file path to open(). 
                    # Refactoring clients to accept bytes would be best, but for now
                    # let's write to temp file.
                    
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=Path(source_item.name).suffix, delete=False) as tmp:
                        tmp.write(input_data)
                        tmp_path = Path(tmp.name)
                    
                    try:
                        # API Call
                        result_data = generator.process_image(
                            tmp_path,
                            style['prompt_text'],
                            style['strength']
                        )
                    finally:
                        try:
                            os.remove(tmp_path)
                        except: pass
                    
                    if result_data:
                        # WRITE Output
                        target_full_path = f"{output_path.rstrip('/')}/{output_filename}"
                        output_provider.write_file(target_full_path, result_data)
                        success_count += 1
                    else:
                        logger.warning(f"Failed to generate {output_filename}")
                        fail_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {output_filename}: {e}")
                    fail_count += 1
                    
                pbar.update(1)
                
        logger.info(f"Completed. Success: {success_count}, Failed: {fail_count}")
        print(f"\nCompleted. Success: {success_count}, Failed: {fail_count}")

    except Exception as e:
        logger.error(f"Critical Error: {e}")
        print(f"Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
