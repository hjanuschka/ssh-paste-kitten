# SSH Drop Upload for Kitty Terminal

A [kitty](https://sw.kovidgoyal.net/kitty/) watcher that automatically uploads files when you **drag & drop** them into an SSH session.

**Normal Cmd+V paste is unchanged** - this only intercepts drag & drop events!

## Features

- 🖱️ **Drag & Drop only** - Normal copy/paste (Cmd+C/V) works as usual
- 🔍 **Auto-detects SSH sessions** - Works with `ssh`, `kitten ssh`, and `mosh`
- 🚀 **Native file transfer** - Uses kitty's built-in transfer protocol with `kitten ssh`
- 📁 **Unique filenames** - Avoids collisions with hash-prefixed names
- 🔒 **Secure** - Files transfer over your existing SSH connection

## Demo

```
# 1. Connect to remote server
kitten ssh user@server

# 2. Drag a file from Finder into the terminal
#    → File is uploaded to /tmp/uploads/
#    → Remote path is pasted

# Example output:
mkdir -p /tmp/uploads && kitten transfer --direction=upload '/path/to/local/file.png' '/tmp/uploads/a1b2c3d4_file.png' && echo '📁 Uploaded: /tmp/uploads/a1b2c3d4_file.png'
```

## Installation

### 1. Download the watcher

```bash
# Create kitty config directory if needed
mkdir -p ~/.config/kitty

# Download
curl -o ~/.config/kitty/ssh_drop_upload.py \
  https://raw.githubusercontent.com/hjanuschka/ssh-paste-kitten/main/ssh_drop_upload.py
```

Or clone the repo:

```bash
git clone https://github.com/hjanuschka/ssh-paste-kitten.git
cp ssh-paste-kitten/ssh_drop_upload.py ~/.config/kitty/
```

### 2. Add to kitty.conf

Add this line to `~/.config/kitty/kitty.conf`:

```conf
# Enable remote control (for kitty @ commands)
allow_remote_control yes

# SSH Drop Upload watcher
watcher ssh_drop_upload.py
```

### 3. Reload kitty config

Press `Ctrl+Shift+F5` to reload the config.

Or if you have `allow_remote_control yes` in your config, run:

```bash
kitty @ load-config
```

**Note:** Watchers only apply to **new windows**. Open a new tab/window after reloading, or restart kitty completely.

## Usage

### Recommended: Use `kitten ssh`

For the best experience with automatic file uploads, use `kitten ssh`:

```bash
# Instead of:
ssh user@server

# Use:
kitten ssh user@server
```

Benefits of `kitten ssh`:
- Native file transfer protocol (fast, works through the terminal)
- Automatic shell integration
- Better terminal features over SSH

### How It Works

1. **Drop files** from Finder/file manager into a kitty window
2. **Watcher detects** if the window is running SSH
3. **If in SSH**: Generates upload command using `kitten transfer`
4. **If not SSH**: Pastes the file paths normally (original behavior)

### Upload Location

Files are uploaded to `/tmp/uploads/<hash>_<filename>`:
- `<hash>` - 8-character unique identifier  
- `<filename>` - Original filename

Example: `/tmp/uploads/a1b2c3d4_screenshot.png`

## Requirements

- [Kitty terminal](https://sw.kovidgoyal.net/kitty/) v0.25.0+
- For native transfer: `kitten ssh` (installs `kitten` on remote automatically)

## Troubleshooting

### Files not uploading?

1. **Check you're using `kitten ssh`** - Native transfer only works with `kitten ssh`
2. **Check the watcher is loaded** - Run `kitty --debug-config 2>&1 | grep watcher`
3. **Restart kitty** after adding the watcher to config

### Want to use plain `ssh`?

The watcher will still detect plain SSH sessions, but will just paste the local paths with a hint to use `scp` manually (since native transfer isn't available).

### Check if watcher is active

```bash
kitty --debug-config 2>&1 | grep -i watcher
```

## How It Works (Technical)

The watcher monkey-patches `Window.on_drop()` in kitty to:

1. Check if dropped content contains `text/uri-list` (file URLs)
2. Parse and validate local file paths
3. Check if foreground process is SSH (`ssh`, `kitten ssh`, `mosh`)
4. If SSH + kitten: Generate `kitten transfer --direction=upload` command
5. If SSH + plain: Paste paths with scp hint
6. If not SSH: Use original `on_drop` behavior

## Files

- `ssh_drop_upload.py` - The watcher (install this one)
- `smart_paste.py` - Alternative kitten for Cmd+V override (not needed for drag & drop)

## Contributing

Contributions welcome! Please open an issue or PR.

## License

MIT License - see [LICENSE](LICENSE)

## Credits

- Built for [kitty terminal](https://sw.kovidgoyal.net/kitty/) by Kovid Goyal
- Uses kitty's excellent [file transfer protocol](https://sw.kovidgoyal.net/kitty/kittens/transfer/)
