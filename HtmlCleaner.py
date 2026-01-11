"""
HTML Cleaner for Sublime Text
Simplifies HTML for email-friendly output.

Usage:
    - Select HTML and run "HTML Cleaner: Clean Selection" from command palette
    - Or use keyboard shortcut (default: Ctrl+Shift+H / Cmd+Shift+H)
    - If no selection, cleans entire file

Installation:
    1. In Sublime: Preferences > Browse Packages...
    2. Create a folder called "HtmlCleaner"
    3. Copy all files into that folder
"""

import sublime
import sublime_plugin
import re
from html.parser import HTMLParser

# =============================================================================
# CONFIGURATION - Edit these to customize cleaning behavior
# =============================================================================

CONFIG = {
    # Tags to keep (everything else gets unwrapped - content kept, tag removed)
    "keep_tags": [
        # Structure
        "p", "br", "hr",
        # Headings
        "h1", "h2", "h3", "h4", "h5", "h6",
        # Inline formatting
        "strong", "b", "em", "i", "u", "s", "strike",
        # Links and images
        "a", "img",
        # Lists
        "ul", "ol", "li",
        # Other
        "blockquote", "pre", "code",
    ],

    # Tags to remove entirely (including their content)
    "remove_with_content": [
        "script", "style", "noscript", "iframe", "object", "embed",
        "form", "input", "button", "select", "textarea",
        "nav", "header", "footer", "aside",
        "svg", "canvas",
    ],

    # Table tags - will be converted to paragraphs
    "table_tags": ["table", "thead", "tbody", "tfoot", "tr", "td", "th"],

    # Attributes to keep (per tag). Use "*" for all tags.
    # Everything not listed here gets stripped.
    "keep_attributes": {
        "a": ["href", "title"],
        "img": ["src", "alt", "width", "height"],
    },

    # Cleaning options (True/False)
    "remove_classes": True,
    "remove_ids": True,
    "remove_inline_styles": True,
    "remove_data_attributes": True,
    "remove_empty_tags": True,
    "remove_comments": True,
    "convert_b_to_strong": True,      # <b> -> <strong>, <i> -> <em>
    "remove_successive_nbsp": True,   # Multiple &nbsp; -> single space
    "remove_span_tags": True,         # Unwrap <span> tags
    "preserve_line_breaks": True,     # Keep some structure in output
    "convert_tables_to_paragraphs": True,  # Convert table rows to <p> tags
}

# =============================================================================
# HTML PARSER AND CLEANER
# =============================================================================

class HtmlCleanerParser(HTMLParser):
    def __init__(self, config):
        super().__init__(convert_charrefs=False)
        self.config = config
        self.output = []
        self.skip_depth = 0  # Track depth when inside removed tags

    def handle_starttag(self, tag, attrs):
        # Check if we're inside a tag being removed entirely
        if self.skip_depth > 0:
            if tag in self.config["remove_with_content"]:
                self.skip_depth += 1
            return

        # Start skipping if this tag should be removed with content
        if tag in self.config["remove_with_content"]:
            self.skip_depth = 1
            return

        # Handle table conversion
        if self.config["convert_tables_to_paragraphs"]:
            if tag in ["table", "thead", "tbody", "tfoot", "tr"]:
                return  # Skip these, just let content through
            if tag in ["td", "th"]:
                self.output.append("<!--CELL_START-->")
                return

        # Handle span removal
        if tag == "span" and self.config["remove_span_tags"]:
            return  # Don't output span, content will still come through

        # Convert b/i to strong/em
        if self.config["convert_b_to_strong"]:
            if tag == "b":
                tag = "strong"
            elif tag == "i":
                tag = "em"

        # Check if tag should be kept
        if tag not in self.config["keep_tags"]:
            return  # Unwrap: skip tag but content will still come through

        # Filter attributes
        filtered_attrs = self._filter_attributes(tag, attrs)

        # Build tag string
        self_closing = tag in ["img", "br", "hr"]
        if filtered_attrs:
            attr_str = " ".join('{}="{}"'.format(k, v) for k, v in filtered_attrs)
            if self_closing:
                self.output.append("<{} {} />".format(tag, attr_str))
            else:
                self.output.append("<{} {}>".format(tag, attr_str))
        else:
            if self_closing:
                self.output.append("<{} />".format(tag))
            else:
                self.output.append("<{}>".format(tag))

    def handle_startendtag(self, tag, attrs):
        # Handle self-closing tags like <img ... /> or <br />
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        # Handle skip depth for removed tags
        if self.skip_depth > 0:
            if tag in self.config["remove_with_content"]:
                self.skip_depth -= 1
            return

        # Handle table conversion
        if self.config["convert_tables_to_paragraphs"]:
            if tag in ["table", "thead", "tbody", "tfoot", "tr"]:
                return
            if tag in ["td", "th"]:
                self.output.append("<!--CELL_END-->")
                return

        # Handle span removal
        if tag == "span" and self.config["remove_span_tags"]:
            return

        # Convert b/i to strong/em
        if self.config["convert_b_to_strong"]:
            if tag == "b":
                tag = "strong"
            elif tag == "i":
                tag = "em"

        # Only output end tag if we're keeping this tag
        if tag in self.config["keep_tags"]:
            self.output.append("</{}>".format(tag))

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        self.output.append(data)

    def handle_entityref(self, name):
        if self.skip_depth > 0:
            return
        self.output.append("&{};".format(name))

    def handle_charref(self, name):
        if self.skip_depth > 0:
            return
        self.output.append("&#{};".format(name))

    def handle_comment(self, data):
        if self.skip_depth > 0:
            return
        if not self.config["remove_comments"]:
            self.output.append("<!--{}-->".format(data))

    def _filter_attributes(self, tag, attrs):
        """Filter attributes based on config."""
        if not attrs:
            return []

        allowed = self.config["keep_attributes"].get(tag, [])
        allowed_global = self.config["keep_attributes"].get("*", [])

        filtered = []
        for name, value in attrs:
            # Skip based on config flags
            if name == "class" and self.config["remove_classes"]:
                continue
            if name == "id" and self.config["remove_ids"]:
                continue
            if name == "style" and self.config["remove_inline_styles"]:
                continue
            if name.startswith("data-") and self.config["remove_data_attributes"]:
                continue

            # Keep if in allowed list for this tag or global
            if name in allowed or name in allowed_global:
                filtered.append((name, value or ""))

        return filtered

    def get_output(self):
        return "".join(self.output)


def convert_cells_to_paragraphs(html):
    """Convert table cell markers to paragraph tags, avoiding duplicates."""
    pattern = r'<!--CELL_START-->(.*?)<!--CELL_END-->'

    def replace_cell(match):
        content = match.group(1).strip()
        if not content:
            return ''
        # Check if content already starts with a p tag
        if re.match(r'^<p(\s|>)', content, re.IGNORECASE):
            return content
        return '<p>{}</p>'.format(content)

    return re.sub(pattern, replace_cell, html, flags=re.DOTALL)


def clean_html(html, config):
    """Main cleaning function."""
    # Parse and rebuild HTML
    parser = HtmlCleanerParser(config)
    try:
        parser.feed(html)
        result = parser.get_output()
    except Exception as e:
        sublime.error_message("HTML Cleaner: Parse error - {}".format(e))
        return html

    # Convert table cells to paragraphs
    if config["convert_tables_to_paragraphs"]:
        result = convert_cells_to_paragraphs(result)

    # Post-processing with regex

    # Remove successive &nbsp;
    if config["remove_successive_nbsp"]:
        result = re.sub(r'(&nbsp;\s*){2,}', ' ', result)
        result = re.sub(r'(\s*&nbsp;\s*)+', ' ', result)

    # Remove empty tags (multiple passes for nested empties)
    if config["remove_empty_tags"]:
        for _ in range(3):  # Multiple passes catch nested empty tags
            result = re.sub(r'<(\w+)[^>]*>\s*</\1>', '', result)

    # Clean up whitespace
    if config["preserve_line_breaks"]:
        # Normalize multiple line breaks
        result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
        # Add line breaks after block elements for readability
        result = re.sub(r'(</(?:p|div|h[1-6]|tr|li|ul|ol|table|blockquote)>)', r'\1\n', result)
    else:
        # Collapse all whitespace
        result = re.sub(r'\s+', ' ', result)

    # Clean up extra spaces
    result = re.sub(r' +', ' ', result)
    if config["preserve_line_breaks"]:
        # Remove spaces between tags but keep newlines
        result = re.sub(r'>[ \t]+<', '><', result)
        result = re.sub(r'>[ \t]+', '>', result)
        result = re.sub(r'[ \t]+<', '<', result)
    else:
        result = re.sub(r'>\s+<', '><', result)
        result = re.sub(r'>\s+', '> ', result)
        result = re.sub(r'\s+<', ' <', result)

    return result.strip()


# =============================================================================
# SUBLIME TEXT COMMANDS
# =============================================================================

class HtmlCleanerCommand(sublime_plugin.TextCommand):
    """Clean HTML in selection or entire file."""

    def run(self, edit):
        # Get selection or entire file
        selections = self.view.sel()

        if len(selections) == 1 and selections[0].empty():
            # No selection - clean entire file
            region = sublime.Region(0, self.view.size())
            original = self.view.substr(region)
            cleaned = clean_html(original, CONFIG)
            self.view.replace(edit, region, cleaned)
            sublime.status_message("HTML Cleaner: Cleaned entire file")
        else:
            # Clean each selection
            for i, sel in enumerate(reversed(selections)):
                if not sel.empty():
                    original = self.view.substr(sel)
                    cleaned = clean_html(original, CONFIG)
                    self.view.replace(edit, sel, cleaned)
            sublime.status_message("HTML Cleaner: Cleaned {} selection(s)".format(len(selections)))