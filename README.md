# HTML Cleaner for Sublime Text

Simplifies complex HTML into clean, email-friendly markup. Strips out modern layout cruft while preserving structure and basic formatting.

## Installation

1. In Sublime Text: **Preferences → Browse Packages...**
2. Create a new folder called `HtmlCleaner`
3. Copy all files from this package into that folder:
   - `HtmlCleaner.py`
   - `HtmlCleaner.sublime-commands`
   - `Default.sublime-keymap`

## Usage

- **Keyboard shortcut:** `Ctrl+Shift+H` (Windows/Linux) or `Cmd+Shift+H` (Mac)
- **Command palette:** `Ctrl+Shift+P` → "HTML Cleaner: Clean Selection"

If you have a selection, only that selection is cleaned. Otherwise, the entire file is cleaned.

## What It Does

**Keeps:**
- Basic structure: `p`, `br`, `hr`
- Headings: `h1` through `h6`
- Formatting: `strong`, `b`, `em`, `i`, `u`
- Links: `a` (with href)
- Images: `img` (with src, alt, dimensions)
- Lists: `ul`, `ol`, `li`
- Tables: `table`, `tr`, `td`, `th` (email-safe)
- Other: `blockquote`, `pre`, `code`

**Removes:**
- `div`, `span`, `section`, `article`, `nav`, `header`, `footer` (unwrapped - content kept)
- `script`, `style`, `form`, `iframe` (removed entirely with content)
- Classes, IDs, inline styles, data attributes
- HTML comments
- Successive `&nbsp;` characters
- Empty tags

**Converts:**
- `<b>` → `<strong>`
- `<i>` → `<em>`

## Configuration

Edit the `CONFIG` dictionary at the top of `HtmlCleaner.py` to customize:

```python
CONFIG = {
    "keep_tags": [...],           # Tags to preserve
    "remove_with_content": [...], # Tags to delete entirely
    "keep_attributes": {...},     # Which attributes to keep per tag
    "remove_classes": True,       # Strip class attributes
    "remove_ids": True,           # Strip id attributes
    "remove_inline_styles": True, # Strip style attributes
    "remove_comments": True,      # Strip HTML comments
    "convert_b_to_strong": True,  # <b> → <strong>, <i> → <em>
    "remove_successive_nbsp": True,
    "remove_span_tags": True,
    "remove_empty_tags": True,
    "preserve_line_breaks": True,
}
```

## Changing the Keyboard Shortcut

Edit `Default.sublime-keymap`:

```json
[
    {
        "keys": ["ctrl+shift+h"],
        "command": "html_cleaner"
    }
]
```

Change `"ctrl+shift+h"` to your preferred key combination.
