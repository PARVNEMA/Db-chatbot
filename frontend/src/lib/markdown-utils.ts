/**
 * Preprocesses markdown text to ensure tables, line breaks, and formatting are properly rendered.
 * Handles:
 * 1. Escaped newlines (e.g. "\\n" strings).
 * 2. LLM single-line compressed tables.
 * 3. Malformed/broken table reconstructions where pipes or headers were split across lines.
 * 4. Ensuring appropriate whitespace before and after markdown tables and headers.
 */
export function preprocessMarkdown(text: string): string {
  if (!text) return "";

  let processed = text;

  // 1. If text contains literal escaped newlines "\\n", convert them to real newlines
  if (processed.includes("\\n")) {
    processed = processed.replace(/\\n/g, "\n");
  }

  // Normalize windows carriage returns
  processed = processed.replace(/\r\n/g, "\n");

  // 2. Check if the text contains a markdown table separator pattern: |---| or |:---|
  const separatorRegex = /\|(?:\s*:?-{2,}:?\s*\|)+/;
  const sepMatch = separatorRegex.exec(processed);

  if (sepMatch && sepMatch.index !== undefined) {
    try {
      const sepIndex = sepMatch.index;
      const sepEndIndex = sepIndex + sepMatch[0].length;

      // Find the start of the table block (scan backwards for the preceding pipe or beginning of paragraph)
      const beforeSep = processed.slice(0, sepIndex);
      const firstPipeBefore = beforeSep.lastIndexOf("\n\n");
      const tableStartIndex = firstPipeBefore !== -1 ? firstPipeBefore + 2 : 0;

      // Find the end of the table block (scan forward for double newline or non-pipe text)
      const afterSep = processed.slice(sepEndIndex);
      // End of table is either at a double newline followed by text without '|', or end of string
      const endMatch = /\n\s*\n(?=[^|]*$)|(?<=\|)\s*\n\s*\n(?=[A-Z|a-z0-9#*_`])/.exec(afterSep);
      const tableEndIndex = endMatch ? sepEndIndex + endMatch.index : processed.length;

      const prefix = processed.slice(0, tableStartIndex).trimEnd();
      const headerPart = processed.slice(tableStartIndex, sepIndex);
      const dataPart = processed.slice(sepEndIndex, tableEndIndex);
      const suffix = processed.slice(tableEndIndex).trimStart();

      // Extract header cells
      const rawHeaderCells = headerPart
        .split(/[\n|]/)
        .map((c) => c.trim())
        .filter((c) => c.length > 0);

      // Extract data cells
      const rawDataCells = dataPart
        .split(/[\n|]/)
        .map((c) => c.trim())
        .filter((c) => c.length > 0 && !/^:?-{2,}:?$/.test(c));

      const numCols = rawHeaderCells.length;

      if (numCols > 0 && rawDataCells.length > 0) {
        const headerRow = `| ${rawHeaderCells.join(" | ")} |`;
        const separatorRow = `| ${Array(numCols).fill("---").join(" | ")} |`;

        const dataRows: string[] = [];
        for (let i = 0; i < rawDataCells.length; i += numCols) {
          const rowCells = rawDataCells.slice(i, i + numCols);
          // Pad row if missing trailing cells
          while (rowCells.length < numCols) {
            rowCells.push("-");
          }
          dataRows.push(`| ${rowCells.join(" | ")} |`);
        }

        const rebuiltTable = [headerRow, separatorRow, ...dataRows].join("\n");
        const parts: string[] = [];
        if (prefix) parts.push(prefix);
        parts.push(rebuiltTable);
        if (suffix) parts.push(suffix);

        processed = parts.join("\n\n");
      }
    } catch {
      // Fallback: simple newline insertion if advanced reconstruction throws
      processed = processed.replace(/\|\s*\|\s*(?=[^|\n]*\|)/g, "|\n|");
    }
  }

  return processed;
}
