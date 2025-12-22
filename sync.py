import os
from pathlib import Path

def get_valid_images(source_dir):
    """
    Generator yielding valid image paths from source directory.
    Supported extensions: .jpg, .jpeg, .png, .webp (can be expanded)
    """
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    source_path = Path(source_dir)
    if not source_path.exists():
        return
    
    for item in source_path.iterdir():
        if item.is_file() and item.suffix.lower() in valid_extensions:
            yield item

def map_expected_state(source_dir, styles):
    """
    Step A: Generate a map of expected output files.
    Returns a dictionary: {output_filename: (source_image_path, style_config)}
    """
    expected_state = {}
    valid_images = list(get_valid_images(source_dir))
    
    for img_path in valid_images:
        for style in styles:
            # Naming convention: {original_filename}_{prompt_index}.{extension}
            # We preserve the original extension or standardized? The spec says {extension} roughly.
            # Let's keep original extension for simplicity.
            output_filename = f"{img_path.stem}_{style['index']}{img_path.suffix}"
            expected_state[output_filename] = {
                'source_path': img_path,
                'style': style,
                'output_filename': output_filename
            }
    
    return expected_state

def clean_output(expected_state, output_dir):
    """
    Step B: Remove orphaned files from output directory.
    Returns: List of deleted filenames (for logging).
    """
    output_path = Path(output_dir)
    deleted_files = []
    
    if not output_path.exists():
        return deleted_files

    for item in output_path.iterdir():
        if item.is_file():
            if item.name not in expected_state:
                try:
                    item.unlink()
                    deleted_files.append(item.name)
                except OSError as e:
                    print(f"Error deleting orphaned file {item.name}: {e}")
                    
    return deleted_files

def get_missing_files(expected_state, output_dir):
    """
    Step C: Identify which files need to be generated.
    Returns: List of task dictionaries (subset of expected_state values).
    """
    output_path = Path(output_dir)
    missing_files = []
    
    for filename, details in expected_state.items():
        target_path = output_path / filename
        if not target_path.exists():
            missing_files.append(details)
            
    return missing_files
