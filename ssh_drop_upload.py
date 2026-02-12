#!/usr/bin/env python3
"""
SSH Drop Upload Watcher for Kitty Terminal

This watcher intercepts file drag & drop events. When files are dropped
into an SSH session (via `kitten ssh`), they are automatically uploaded
to the remote server and the remote path is pasted instead.

Normal Cmd+C/Cmd+V behavior is unchanged - this ONLY affects drag & drop!

Installation:
1. Copy this file to ~/.config/kitty/ssh_drop_upload.py
2. Add to kitty.conf:
   watcher ssh_drop_upload.py

For best experience, use `kitten ssh user@host` instead of `ssh`.
"""

import os
import hashlib
import time
import shlex
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse


def on_load(boss: 'Boss', data: Dict[str, Any]) -> None:
    """
    Called once when the watcher is loaded.
    We monkey-patch the Window.on_drop method here.
    """
    from kitty.window import Window
    
    # Store the original on_drop method
    _original_on_drop = Window.on_drop
    
    def smart_on_drop(self, drop: Dict[str, bytes]) -> None:
        """
        Custom on_drop handler that uploads files when in SSH sessions.
        """
        # Check for URI list (file drops)
        uri_list = drop.get('text/uri-list', b'')
        
        if not uri_list:
            # No file URIs - use original behavior
            return _original_on_drop(self, drop)
        
        # Parse the URIs
        urls = parse_uri_list(uri_list.decode('utf-8', 'replace'))
        
        # Filter for local file paths
        local_files = []
        for url in urls:
            path = url_to_local_path(url)
            if path and os.path.exists(path):
                local_files.append(path)
        
        # If no local files, use original behavior
        if not local_files:
            return _original_on_drop(self, drop)
        
        # Check if we're in an SSH session
        ssh_info = check_ssh_session(self)
        
        if not ssh_info['is_ssh']:
            # Not in SSH - use original behavior (paste paths)
            return _original_on_drop(self, drop)
        
        # We're in SSH with local files - upload them!
        handle_ssh_upload(self, local_files, ssh_info)
    
    # Replace the method
    Window.on_drop = smart_on_drop


def parse_uri_list(text: str) -> List[str]:
    """Parse text/uri-list format (one URI per line, # for comments)."""
    urls = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)
    return urls


def url_to_local_path(url: str) -> Optional[str]:
    """Convert a file:// URL to a local path."""
    if url.startswith('file://'):
        # Parse and decode the URL
        parsed = urlparse(url)
        path = unquote(parsed.path)
        # Handle file://localhost/path or file:///path
        if parsed.netloc and parsed.netloc != 'localhost':
            return None  # Remote file URL, not local
        return path
    elif url.startswith('/'):
        # Already a path
        return url
    return None


def check_ssh_session(window) -> Dict[str, Any]:
    """Check if the window's foreground process is SSH."""
    info = {
        'is_ssh': False,
        'is_kitten_ssh': False,
        'host': None
    }
    
    try:
        for proc in window.child.foreground_processes:
            cmdline = list(proc.get('cmdline') or [])
            if not cmdline:
                continue
            
            cmd = os.path.basename(cmdline[0]).lower()
            
            # kitten ssh (best - supports file transfer)
            if cmd == 'kitten':
                if len(cmdline) > 1 and cmdline[1] in ('ssh', 'run-shell'):
                    info['is_ssh'] = True
                    info['is_kitten_ssh'] = True
                    # Try to find host
                    for arg in cmdline[2:]:
                        if not arg.startswith('-'):
                            if '@' in arg or '.' in arg:
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


def handle_ssh_upload(window, files: List[str], ssh_info: Dict[str, Any]) -> None:
    """
    Handle uploading files to the remote server.
    """
    upload_dir = "/tmp/uploads"
    
    if ssh_info['is_kitten_ssh']:
        # Use kitty's native file transfer protocol
        # This runs `kitten transfer` on the remote which pulls from local
        
        remote_paths = []
        upload_cmds = []
        
        for fpath in files:
            fname = os.path.basename(fpath)
            uid = hashlib.md5(f"{fpath}{time.time_ns()}".encode()).hexdigest()[:8]
            rpath = f"{upload_dir}/{uid}_{fname}"
            remote_paths.append(rpath)
            
            # Escape paths for shell
            local_escaped = shlex.quote(fpath)
            remote_escaped = shlex.quote(rpath)
            
            # kitten transfer upload command (run on remote, pulls from local)
            upload_cmds.append(f"kitten transfer --direction=upload {local_escaped} {remote_escaped}")
        
        # Build command: create dir, transfer files, echo paths
        full_cmd = f"mkdir -p {upload_dir}"
        for cmd in upload_cmds:
            full_cmd += f" && {cmd}"
        
        # Echo the remote paths for easy use
        paths_str = ' '.join(shlex.quote(p) for p in remote_paths)
        full_cmd += f" && echo '📁 Uploaded: {paths_str}'"
        full_cmd += "\n"
        
        window.paste_text(full_cmd)
        
    else:
        # Regular SSH without native transfer
        # Just paste the paths with a helpful hint
        paths_str = ' '.join(shlex.quote(f) for f in files)
        host = ssh_info.get('host') or 'HOST'
        
        window.paste_text(paths_str)
        window.paste_text(f"  # ⬆️  Local paths - use: scp {shlex.quote(files[0])} {host}:{upload_dir}/\n")
