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
        self.pretext_depth = 0  # Track depth when inside hidden pretext
        self.pretext_content = []  # Collect pretext content temporarily
        self.pretexts = []  # Store all found pretexts
        self.bold_tag_stack = []  # Track tags that have font-weight: bold
        self.links = []  # Store unique URLs in order found
        self.link_set = set()  # Track seen URLs for deduplication

    def _is_hidden_pretext(self, attrs):
        """Check if element has CSS indicating hidden pretext."""
        for name, value in attrs:
            if name == "style" and value:
                style_lower = value.lower()
                # Check for common hidden element patterns
                if any(pattern in style_lower for pattern in [
                    "display: none", "display:none",
                    "visibility: hidden", "visibility:hidden",
                    "mso-hide: all", "mso-hide:all",
                    "max-height: 0", "max-height:0",
                    "opacity: 0", "opacity:0",
                ]):
                    return True
        return False

    def _has_bold_style(self, attrs):
        """Check if element has font-weight: bold in style."""
        for name, value in attrs:
            if name == "style" and value:
                style_lower = value.lower()
                if "font-weight: bold" in style_lower or "font-weight:bold" in style_lower:
                    return True
        return False

    def _is_tracking_pixel(self, attrs):
        """Check if img is a 1x1 tracking pixel."""
        width_1 = False
        height_1 = False
        for name, value in attrs:
            if name == "width" and value in ["1", "1px"]:
                width_1 = True
            elif name == "height" and value in ["1", "1px"]:
                height_1 = True
            elif name == "style" and value:
                style_lower = value.lower()
                if re.search(r'width:\s*1px', style_lower):
                    width_1 = True
                if re.search(r'height:\s*1px', style_lower):
                    height_1 = True
        return width_1 and height_1

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

        # Check for hidden pretext
        if self.pretext_depth > 0:
            self.pretext_depth += 1
            return
        if self._is_hidden_pretext(attrs):
            self.pretext_depth = 1
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

        # Remove 1x1 tracking pixel images
        if tag == "img" and self._is_tracking_pixel(attrs):
            return

        # Convert b/i to strong/em
        if self.config["convert_b_to_strong"]:
            if tag == "b":
                tag = "strong"
            elif tag == "i":
                tag = "em"

        # Check if tag should be kept
        if tag not in self.config["keep_tags"]:
            return  # Unwrap: skip tag but content will still come through

        # Handle anchor tags specially - extract URL and use [link] tags
        if tag == "a":
            href = None
            for name, value in attrs:
                if name == "href":
                    href = value
                    break
            if href:
                # Add to unique links list
                if href not in self.link_set:
                    self.link_set.add(href)
                    self.links.append(href)
            self.output.append("[link]")
            return

        # Filter attributes
        filtered_attrs = self._filter_attributes(tag, attrs)

        # Check if this tag has bold styling
        is_bold = self._has_bold_style(attrs)
        if is_bold:
            self.bold_tag_stack.append(tag)

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

        # Add <b> after opening tag if bold styled
        if is_bold and not self_closing:
            self.output.append("<b>")

    def handle_startendtag(self, tag, attrs):
        # Handle self-closing tags like <img ... /> or <br />
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        # Handle skip depth for removed tags
        if self.skip_depth > 0:
            if tag in self.config["remove_with_content"]:
                self.skip_depth -= 1
            return

        # Handle pretext depth
        if self.pretext_depth > 0:
            self.pretext_depth -= 1
            if self.pretext_depth == 0:
                # Store collected pretext for output at top
                pretext = "".join(self.pretext_content).strip()
                # Strip &nbsp; from beginning and end
                pretext = re.sub(r'^(\s*&nbsp;\s*)+', '', pretext)
                pretext = re.sub(r'(\s*&nbsp;\s*)+$', '', pretext)
                pretext = pretext.strip()
                if pretext:
                    self.pretexts.append(pretext)
                self.pretext_content = []
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
            # Handle anchor tags specially
            if tag == "a":
                self.output.append("[/link]")
                return
            # Close </b> before closing tag if it was bold styled
            if self.bold_tag_stack and self.bold_tag_stack[-1] == tag:
                self.output.append("</b>")
                self.bold_tag_stack.pop()
            self.output.append("</{}>".format(tag))

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        if self.pretext_depth > 0:
            self.pretext_content.append(data)
            return
        self.output.append(data)

    def handle_entityref(self, name):
        if self.skip_depth > 0:
            return
        if self.pretext_depth > 0:
            self.pretext_content.append("&{};".format(name))
            return
        self.output.append("&{};".format(name))

    def handle_charref(self, name):
        if self.skip_depth > 0:
            return
        if self.pretext_depth > 0:
            self.pretext_content.append("&#{};".format(name))
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

    def get_pretexts(self):
        return self.pretexts

    def get_links(self):
        return self.links


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
        pretexts = parser.get_pretexts()
        links = parser.get_links()
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

    result = result.strip()

    # Build header with pretexts and links
    header_parts = []

    # Add pretexts first
    if pretexts:
        pretext_block = "\n".join("Pretext: {}".format(p) for p in pretexts)
        header_parts.append(pretext_block)

    # Add unique links after pretexts
    if links:
        links_block = "Links:\n" + "\n".join(links)
        header_parts.append(links_block)

    # Prepend header to result
    if header_parts:
        header = "\n\n".join(header_parts)
        result = header + "\n\n\n" + result

    return result


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