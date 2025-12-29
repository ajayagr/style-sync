import argparse
import sys
import os
import time
from datetime import datetime
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
from stylesync.reporting import RunContext

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
            return LocalStorageProvider(), path, "Local", existing_token
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
            return OneDriveStorageProvider(token), path, "OneDrive", token
        else:
            print("Invalid choice.")

def main():
    # Initialize Reporting Context
    context = RunContext()
    
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
        context.input_type = "Local"
        
        output_provider = LocalStorageProvider()
        output_path = args.output
        context.output_type = "Local"
        
        context.username = os.environ.get("USERNAME", "Local User")
    else:
        # Interactive Mode
        current_token = None
        
        source_provider, source_path, context.input_type, current_token = select_provider("Source", current_token)
        output_provider, output_path, context.output_type, current_token = select_provider("Output", current_token)

        # Try to fetch username if OneDrive
        if isinstance(source_provider, OneDriveStorageProvider):
            context.username = source_provider.get_user_name()
        elif isinstance(output_provider, OneDriveStorageProvider):
            context.username = output_provider.get_user_name()
    
    context.input_path = source_path
    context.output_path = output_path

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
    
    try:
        # Step A: Map Expected State
        print("\nScanning state...")
        expected_state = map_expected_state(source_provider, source_path, styles)
        
        # Populate context stats
        unique_sources = set()
        for v in expected_state.values():
            unique_sources.add(v['source_item'].name)
        
        context.files_found = len(unique_sources)
        context.expected_variants = len(expected_state)
        
        print(f"Expected output files: {len(expected_state)}")
        
        # Step B: Clean Output
        deleted = clean_output(output_provider, expected_state, output_path)
        context.orphan_variants = deleted
        if deleted:
            print(f"Cleaned {len(deleted)} orphaned files.")
            
        # Step C: Generate Missing
        tasks = get_missing_files(output_provider, expected_state, output_path)
        context.missing_variants = [t.get('output_path', '') for t in tasks]
        print(f"Tasks to process: {len(tasks)}")
        
        if not tasks:
            print("All synchronized. No processing needed.")
            # Still generate report for audit
        else:
            # Process tasks
            print("\nProcessing images...")
            success_count = 0
            fail_count = 0
            copy_count = 0
            
            with tqdm(total=len(tasks)) as pbar:
                for task in tasks:
                    step_start = time.time()
                    source_item = task['source_item']
                    is_original = task.get('is_original', False)
                    target_full_path = task.get('full_target_path')
                    output_rel_path = task.get('output_path', '')
                    
                    if is_original:
                        # Direct copy for original folder
                        pbar.set_description(f"Copying {source_item.name}")
                        try:
                            input_data = source_provider.read_file(source_item.path)
                            output_provider.write_file(target_full_path, input_data)
                            copy_count += 1
                        except Exception as e:
                            logger.error(f"Error copying {source_item.name}: {e}")
                            fail_count += 1
                        pbar.update(1)
                        continue
                    
                    # Styled variant processing
                    style = task['style']
                    display_name = source_item.name
                    step_name = f"{display_name} -> {style['name']}"
                    
                    pbar.set_description(f"Processing {step_name}")
                    
                    try:
                        # READ Source
                        input_data = source_provider.read_file(source_item.path)
                        import tempfile
                        
                        # Fix for windows named temp file open issue: close it first
                        tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=Path(source_item.name).suffix)
                        os.close(tmp_fd)
                        tmp_path = Path(tmp_path_str)
                        
                        try:
                            # Write data to temp
                            with open(tmp_path, 'wb') as f:
                                f.write(input_data)

                            # API Call
                            result = generator.process_image(
                                tmp_path,
                                style['prompt_text'],
                                style['strength']
                            )
                            
                            # Log the step
                            context.add_step(
                                name=step_name,
                                start_time=step_start,
                                details=f"Request:\n{result.request_info}\n\nResponse:\n{result.response_info}",
                                error=None if result.data else "API returned no data"
                            )

                        finally:
                            if tmp_path.exists():
                                os.remove(tmp_path)
                        
                        if result and result.data:
                            # WRITE Output
                            output_provider.write_file(target_full_path, result.data)
                            success_count += 1
                        else:
                            logger.warning(f"Failed to generate {output_rel_path}")
                            fail_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing {output_rel_path}: {e}")
                        context.add_step(name=step_name, start_time=step_start, details="Exception occurred", error=str(e))
                        fail_count += 1
                        
                    pbar.update(1)
                    
            logger.info(f"Completed. Copied: {copy_count}, Styled: {success_count}, Failed: {fail_count}")
            print(f"\nCompleted. Copied: {copy_count}, Styled: {success_count}, Failed: {fail_count}")

    except Exception as e:
        logger.error(f"Critical Error: {e}")
        print(f"Critical Error: {e}")
        # Dont exit yet, try to save report
        
    finally:
        # Generate Report
        try:
            report_content = context.generate_markdown()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"report_{timestamp}.md"
            
            # Save report to stylesync/report folder locally
            report_dir = Path("stylesync/report")
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / report_filename
            
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
                
            print(f"\nReport generated: {report_path.absolute()}")
        except Exception as e:
            print(f"Failed to save report: {e}")

if __name__ == "__main__":
    main()
