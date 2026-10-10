

def copy_files_to_folder(source_folder: str, destination_folder: str) -> None:
    """Copy files from source_folder to destination_folder."""
    import shutil
    import os

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    for filename in os.listdir(source_folder):
        source_file = os.path.join(source_folder, filename)
        destination_file = os.path.join(destination_folder, filename)
        if os.path.isfile(source_file):
            shutil.copy2(source_file, destination_file)
            print(f"Copied: {source_file} → {destination_file}")



def remove_folder(folder_path: str) -> None:
    """Remove a folder and all its contents."""
    import shutil
    import os

    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        print(f"Removed folder: {folder_path}")
    else:
        print(f"Folder not found: {folder_path}")