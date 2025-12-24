from .storage import StorageProvider

def get_valid_images(provider: StorageProvider, source_dir: str):
    """
    Generator yielding valid FileItem objects from source directory.
    Supported extensions: .jpg, .jpeg, .png, .webp
    """
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    if not provider.exists(source_dir):
        return
    
    for item in provider.list_files(source_dir):
        if not item.is_dir and any(item.name.lower().endswith(ext) for ext in valid_extensions):
            yield item

def map_expected_state(source_provider: StorageProvider, source_dir: str, styles):
    """
    Step A: Generate a map of expected output files.
    Returns a dictionary: {output_filename: (source_item, style_config)}
    """
    expected_state = {}
    valid_images = list(get_valid_images(source_provider, source_dir))
    
    for item in valid_images:
        for style in styles:
            # Construct output filename
            # Assume item.name has extension
            name_parts = item.name.rsplit('.', 1)
            stem = name_parts[0]
            suffix = f".{name_parts[1]}" if len(name_parts) > 1 else ""
            
            output_filename = f"{stem}_{style['index']}{suffix}"
            expected_state[output_filename] = {
                'source_item': item,
                'style': style,
                'output_filename': output_filename
            }
    
    return expected_state

def clean_output(dest_provider: StorageProvider, expected_state, output_dir: str):
    """
    Step B: Remove orphaned files from output directory.
    Returns: List of deleted filenames.
    """
    deleted_files = []
    
    if not dest_provider.exists(output_dir):
        return deleted_files

    for item in dest_provider.list_files(output_dir):
        if not item.is_dir:
            if item.name not in expected_state:
                try:
                    dest_provider.delete_file(item.path)
                    deleted_files.append(item.name)
                except Exception as e:
                    print(f"Error deleting orphaned file {item.name}: {e}")
                    
    return deleted_files

def get_missing_files(dest_provider: StorageProvider, expected_state, output_dir: str):
    """
    Step C: Identify which files need to be generated.
    Returns: List of task dictionaries.
    """
    missing_files = []
    
    for filename, details in expected_state.items():
        # Check if exists in output
        # item.path depends on provider, but list_files returns relative-ish path usually?
        # Provider usually needs full path to check existence.
        # Assuming output_dir + filename
        
        target_path = f"{output_dir.rstrip('/')}/{filename}"
        
        if not dest_provider.exists(target_path):
            missing_files.append(details)
            
    return missing_files
