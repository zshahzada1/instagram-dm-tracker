# Instagram DM Media Tracker

A tool to track media (reels, posts, carousels, stories) shared in an Instagram DM thread.

## Features

- **Scan thread**: Automatically scan an Instagram DM thread and detect new media items
- **Store media**: Save detected media (reels, posts, carousels, stories) to a local SQLite database
- **Auto-react**: Automatically react to new items as they're discovered
- **Real browser**: Uses Camoufox (Firefox-based, anti-detect) for realistic browser automation
- **Safe interaction**: Only uses DOM-clicking for reactions - never constructs API calls

## Tech Stack

- **Python 3** + **Camoufox** (Firefox-based browser automation)
- **Playwright** for browser control
- **SQLite** for local data storage
- **React UI** (coming soon)

## Requirements

- Python 3.10+
- Windows 11
- See `requirements.txt` for Python packages

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

See `CLAUDE.md` for detailed architecture, API details, and development status.

### Current Status

- **Phase 2 Complete**: Instagram API recon and reaction DOM-click implementation verified
- **Ready for Phase 3**: Scanner implementation with database integration

### Key Files

- `CLAUDE.md` - Project overview and architecture rules
- `docs/` - Documentation, API findings, and schema design
- `scripts/` - Python scripts for login, recon, and reaction testing
- `test-cookies/` - Instagram session cookies (not committed to git)

## Architecture

This project uses a real browser (Camoufox) driven by Playwright. There are exactly two ways we interact with Instagram:

1. **READS** - Navigate and scroll normally, intercept GraphQL responses passively
2. **WRITES (reactions only)** - DOM-click the actual Instagram UI (never POST to `/api/graphql`)

## Development Notes

- **Headed browser only**: Always uses `headless=False` for realistic behavior
- **Human-like pacing**: Random delays between actions to avoid detection
- **Blocker detection**: Automatically detects and stops on Instagram checkpoints/captchas
- **Privacy**: All sensitive files (cookies, artifacts) are excluded from git

## License

MIT License - See LICENSE file for details
