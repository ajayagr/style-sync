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
    
    New Structure:
    - output_dir/original/<filename>  (copy of source)
    - output_dir/<style_name>/<filename>  (styled variant)
    
    Returns a dictionary: {relative_path: {source_item, style, output_path, is_original}}
    """
    expected_state = {}
    valid_images = list(get_valid_images(source_provider, source_dir))
    
    for item in valid_images:
        # 1. Add original copy entry
        original_key = f"original/{item.name}"
        expected_state[original_key] = {
            'source_item': item,
            'style': None,
            'output_path': original_key,
            'is_original': True
        }
        
        # 2. Add styled variant entries
        for style in styles:
            style_name = style.get('name', f"style_{style['index']}")
            # Sanitize folder name (replace spaces with underscores, lowercase)
            style_folder = style_name.replace(' ', '_').lower()
            
            style_key = f"{style_folder}/{item.name}"
            expected_state[style_key] = {
                'source_item': item,
                'style': style,
                'output_path': style_key,
                'is_original': False
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

    # List all files recursively in output_dir
    for item in dest_provider.list_files(output_dir):
        if not item.is_dir:
            # Get relative path from output_dir
            rel_path = item.path
            if rel_path.startswith(output_dir):
                rel_path = rel_path[len(output_dir):].lstrip('/')
            
            if rel_path not in expected_state:
                try:
                    dest_provider.delete_file(item.path)
                    deleted_files.append(rel_path)
                except Exception as e:
                    print(f"Error deleting orphaned file {rel_path}: {e}")
                    
    return deleted_files

def get_missing_files(dest_provider: StorageProvider, expected_state, output_dir: str):
    """
    Step C: Identify which files need to be generated/copied.
    Returns: List of task dictionaries.
    """
    missing_files = []
    
    for rel_path, details in expected_state.items():
        target_path = f"{output_dir.rstrip('/')}/{rel_path}"
        
        if not dest_provider.exists(target_path):
            # Add full target path to details
            details_copy = details.copy()
            details_copy['full_target_path'] = target_path
            missing_files.append(details_copy)
            
    return missing_files
