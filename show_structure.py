import os

# Folders to completely skip
EXCLUDE_DIRS = {'venv', '.git', '__pycache__', 'node_modules', 'dist', 'build', 'site-packages', 'env', '.idea', '.vscode'}

# Only show these file extensions
ALLOWED_EXT = {'.py', '.html'}

def should_show_file(filename):
    return any(filename.endswith(ext) for ext in ALLOWED_EXT)

def print_tree(startpath, prefix=''):
    entries = sorted(os.listdir(startpath))
    # Filter out excluded directories and non-allowed files
    items = []
    for e in entries:
        full = os.path.join(startpath, e)
        if os.path.isdir(full):
            if e not in EXCLUDE_DIRS:
                items.append((e, True))
        else:
            if should_show_file(e):
                items.append((e, False))
    # Print with tree indentation
    for i, (name, is_dir) in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = '└── ' if is_last else '├── '
        print(prefix + connector + name + ('/' if is_dir else ''))
        if is_dir:
            extension = '    ' if is_last else '│   '
            print_tree(os.path.join(startpath, name), prefix + extension)

if __name__ == '__main__':
    print('.')
    print_tree('.')
