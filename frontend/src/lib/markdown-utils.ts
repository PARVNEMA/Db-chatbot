/**
 * Preprocesses markdown text to ensure tables and formatting are properly rendered.
 * LLMs frequently compress markdown tables onto a single line or omit line breaks
 * before and after tables, which breaks standard GFM table parsing.
 */
export function preprocessMarkdown(text: string): string {
  if (!text) return "";

  let processed = text;

  // Check if text contains a markdown table separator pattern: |---|---|
  if (/\|\s*:?-{2,}:?\s*\|/.test(processed)) {
    // 1. Split adjacent row boundaries: replace "| |" or "|   |" with "|\n|"
    processed = processed.replace(/\|\s*\|(?=[^|])/g, "|\n|");

    // 2. Ensure double newline before table starts if preceded by text without a newline
    processed = processed.replace(/([^\n])\s*(\|(?:\s*[^|\n]+\s*\|){2,})/g, (match, p1, p2) => {
      if (p1 === "|") return match;
      return `${p1}\n\n${p2}`;
    });

    // 3. Ensure double newline after the table ends if followed by text on the same line
    // e.g. "| 29 999.00 | If you want to..." -> "| 29 999.00 |\n\nIf you want to..."
    processed = processed.replace(/(\|\s*)([A-Za-z0-9`'"*_[])/g, (match, p1, p2, offset, fullStr) => {
      const prevSlice = fullStr.slice(0, offset);
      // If the preceding text ends with a pipe-delimited segment (table cell)
      if (/\|[^|\n]*$/.test(prevSlice)) {
        return `${p1.trim()}\n\n${p2}`;
      }
      return match;
    });
  }

  return processed;
}
