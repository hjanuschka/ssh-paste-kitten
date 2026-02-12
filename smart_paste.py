#!/usr/bin/env python3
"""
Smart Paste Kitten for Kitty Terminal

When dropping/pasting local file paths in an SSH session (via `kitten ssh`),
this kitten uploads the files to the remote server and pastes the remote path.

The upload uses kitty's file transfer protocol (escape sequences over TTY),
which works transparently when connected via `kitten ssh`.

Usage in kitty.conf:
    map cmd+v kitten smart_paste.py
    
    # Required for this to work:
    allow_remote_control yes

For best experience:
- Use `kitten ssh user@host` instead of plain `ssh`
- The remote needs `kitten` available (auto-installed by kitten ssh)
"""

import os
import subprocess
import hashlib
import time
from typing import List, Optional, Dict, Any
from urllib.parse import unquote


def main(args: List[str]) -> Optional[str]:
    """Kitten entry point - we don't need overlay UI."""
    pass


def get_clipboard() -> str:
    """Get system clipboard contents."""
    cmds = [
        ['pbpaste'],
        ['xclip', '-selection', 'clipboard', '-o'],
        ['xsel', '--clipboard', '--output'],
        ['wl-paste'],
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except Exception:
            pass
    return ''


def extract_file_paths(text: str) -> List[str]:
    """Extract valid local file paths from clipboard text."""
    paths = []
    for line in text.strip().split('\n'):
        path = line.strip()
        
        # Handle file:// URLs (from Finder drag-drop)
        if path.startswith('file://'):
            path = unquote(path[7:])
        
        # Handle quoted paths
        if (path.startswith('"') and path.endswith('"')) or \
           (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        
        # Validate it's a real file/directory
        if path and os.path.exists(path):
            paths.append(os.path.abspath(path))
    
    return paths


def is_ssh_window(window) -> Dict[str, Any]:
    """Check if window runs SSH and gather info."""
    info = {
        'is_ssh': False,
        'is_kitten_ssh': False,
        'host': None,
        'pid': None
    }
    
    try:
        for proc in window.child.foreground_processes:
            cmdline = list(proc.get('cmdline') or [])
            if not cmdline:
                continue
            
            cmd = os.path.basename(cmdline[0]).lower()
            info['pid'] = proc.get('pid')
            
            # kitten ssh - supports file transfer
            if cmd == 'kitten':
                if len(cmdline) > 1 and cmdline[1] in ('ssh', 'run-shell'):
                    info['is_ssh'] = True
                    info['is_kitten_ssh'] = True
                    # Find host
                    for arg in cmdline[2:]:
                        if not arg.startswith('-') and '@' in arg:
                            info['host'] = arg
                            break
                        elif not arg.startswith('-') and '.' in arg:
                            info['host'] = arg
                            break
                    return info
            
            # Regular ssh
            elif cmd == 'ssh':
                info['is_ssh'] = True
                for arg in reversed(cmdline[1:]):
                    if not arg.startswith('-'):
                        info['host'] = arg
                        break
                return info
            
            # mosh
            elif cmd in ('mosh', 'mosh-client'):
                info['is_ssh'] = True
                return info
    except Exception:
        pass
    
    return info


def handle_result(args: List[str], answer: Optional[str], target_window_id: int, boss) -> None:
    """
    Main handler - processes paste, detects files, uploads if in SSH.
    """
    window = boss.window_id_map.get(target_window_id)
    if not window:
        return
    
    # Get clipboard content
    clipboard = get_clipboard()
    if not clipboard:
        clipboard = boss.current_primary_selection_or_clipboard or ''
    if not clipboard:
        return
    
    # Look for file paths
    files = extract_file_paths(clipboard)
    
    # No files → regular paste
    if not files:
        window.paste_text(clipboard)
        return
    
    # Check if in SSH
    ssh = is_ssh_window(window)
    
    if not ssh['is_ssh']:
        # Not SSH → regular paste
        window.paste_text(clipboard)
        return
    
    # ═══════════════════════════════════════════════════════
    # We're in SSH and have local file paths to upload!
    # ═══════════════════════════════════════════════════════
    
    upload_dir = "/tmp/uploads"
    
    if ssh['is_kitten_ssh']:
        # Best case: kitten ssh supports native file transfer!
        # We send the command to the remote shell that will use
        # `kitten transfer --direction=upload` to receive files from local
        
        remote_paths = []
        upload_cmds = []
        
        for fpath in files:
            fname = os.path.basename(fpath)
            uid = hashlib.md5(f"{fpath}{time.time_ns()}".encode()).hexdigest()[:8]
            rpath = f"{upload_dir}/{uid}_{fname}"
            remote_paths.append(rpath)
            
            # Quote the local path properly for the shell
            local_escaped = fpath.replace("'", "'\"'\"'")
            remote_escaped = rpath.replace("'", "'\"'\"'")
            
            # kitten transfer upload command (run on remote, pulls from local)
            upload_cmds.append(f"kitten transfer --direction=upload '{local_escaped}' '{remote_escaped}'")
        
        # Build the full command sequence
        # 1. Create upload directory
        # 2. Transfer each file
        # 3. Echo the paths for easy copy
        
        full_cmd = f"mkdir -p {upload_dir}"
        for cmd in upload_cmds:
            full_cmd += f" && {cmd}"
        
        # Add a final echo of the paths
        paths_str = ' '.join(f"'{p}'" for p in remote_paths)
        full_cmd += f" && echo 'Uploaded: {paths_str}'"
        full_cmd += "\n"
        
        # Send to the terminal
        window.paste_text(full_cmd)
        
    else:
        # Regular SSH - no native transfer support
        # Option 1: Offer to use scp (but we can't easily do that from here)
        # Option 2: Just paste paths with a helpful message
        
        paths_str = ' '.join(f"'{f}'" for f in files)
        
        # Paste the local paths
        window.paste_text(paths_str)
        
        # Add a comment hint
        hint = f"  # Local path(s) - upload with: scp {files[0]} {ssh['host'] or 'host'}:/tmp/"
        window.paste_text(hint + "\n")
