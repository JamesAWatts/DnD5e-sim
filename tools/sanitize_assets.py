import os
import re
import sys

def sanitize_assets(root_dir="assets"):
    """
    Recursively renames all files and directories in root_dir to lowercase.
    Uses topdown=False to ensure we rename children before parents.
    """
    assets_path = os.path.abspath(root_dir)
    if not os.path.exists(assets_path):
        print(f"[ERROR] Assets directory not found at: {assets_path}")
        return

    print(f"[PROCESS] Renaming all assets in {assets_path} to lowercase...")
    
    count = 0
    for root, dirs, files in os.walk(assets_path, topdown=False):
        # Rename files first
        for name in files:
            if name != name.lower():
                old_path = os.path.join(root, name)
                new_path = os.path.join(root, name.lower())
                try:
                    os.rename(old_path, new_path)
                    count += 1
                except Exception as e:
                    print(f"  [!] Failed to rename file: {old_path} -> {e}")

        # Rename directories
        for name in dirs:
            if name != name.lower():
                old_path = os.path.join(root, name)
                new_path = os.path.join(root, name.lower())
                try:
                    os.rename(old_path, new_path)
                    count += 1
                except Exception as e:
                    print(f"  [!] Failed to rename directory: {old_path} -> {e}")

    print(f"[COMPLETE] Renamed {count} items to lowercase.")

def scan_python_files(project_root="."):
    """
    Scans Python files for hardcoded asset paths with uppercase letters or backslashes.
    """
    print(f"[PROCESS] Scanning .py files in {os.path.abspath(project_root)} for unsafe paths...")
    
    # Pattern to find strings that look like asset/data paths
    # Matches strings starting with assets/ or data/ or containing common asset extensions
    path_pattern = re.compile(r"['\"](?P<path>.*?(assets|data).*?)['\"]", re.IGNORECASE)
    
    issue_count = 0
    for root, dirs, files in os.walk(project_root):
        # Skip hidden dirs and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env']]
        
        for name in files:
            if name.endswith('.py') and name != 'sanitize_assets.py':
                file_path = os.path.join(root, name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    for i, line in enumerate(lines):
                        matches = path_pattern.finditer(line)
                        for match in matches:
                            path_str = match.group('path')
                            
                            has_backslash = '\\' in path_str
                            has_uppercase = any(c.isupper() for c in path_str)
                            
                            if has_backslash or has_uppercase:
                                rel_path = os.path.relpath(file_path, project_root)
                                print(f"[WARNING] {rel_path}:{i+1}")
                                print(f"  Line: {line.strip()}")
                                if has_backslash:
                                    print("  Issue: Backslash '\' found. Use '/' or os.path.join().")
                                if has_uppercase:
                                    print("  Issue: Uppercase letters found. Linux is case-sensitive.")
                                print("-" * 40)
                                issue_count += 1
                except Exception as e:
                    print(f"  [!] Could not read {file_path}: {e}")

    print(f"[COMPLETE] Scan finished. Found {issue_count} potential path issues.")

if __name__ == "__main__":
    # 1. Rename assets to lowercase
    sanitize_assets("assets")
    
    # 2. Also sanitize data folder (highly recommended for Linux/Web)
    if os.path.exists("data"):
        sanitize_assets("data")
        
    # 3. Scan code for bad habits
    print("\n" + "="*50 + "\n")
    scan_python_files(".")
    
    print("\n[HINT] Always use core.game_rules.path_utils.get_resource_path() to wrap your paths!")
