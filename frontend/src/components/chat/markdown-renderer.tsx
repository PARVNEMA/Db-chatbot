"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { preprocessMarkdown } from "@/lib/markdown-utils";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

interface CodeBlockProps {
  children?: React.ReactNode;
  className?: string;
}

function CodeBlock({ children, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const codeText = String(children).replace(/\n$/, "");
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1] : "";

  const handleCopy = () => {
    navigator.clipboard.writeText(codeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-2.5 rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-sm">
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900/80 border-b border-zinc-800/80 text-[11px] font-mono text-zinc-400">
        <span>{language || "code"}</span>
        <Button
          size="icon-xs"
          variant="ghost"
          onClick={handleCopy}
          className="h-5 w-5 text-zinc-400 hover:text-white"
          title="Copy code"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
        </Button>
      </div>
      <pre className="p-3 overflow-x-auto font-mono text-xs text-emerald-400 leading-relaxed">
        <code>{codeText}</code>
      </pre>
    </div>
  );
}

export function MarkdownRenderer({
  content,
  className = "",
}: MarkdownRendererProps): React.JSX.Element {
  const processed = preprocessMarkdown(content);

  return (
    <div className={`text-sm text-zinc-200 leading-relaxed font-sans ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children, ...props }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950/80 shadow-md">
              <table className="w-full border-collapse text-left text-xs font-mono" {...props}>
                {children}
              </table>
            </div>
          ),
          thead: ({ children, ...props }) => (
            <thead
              className="border-b border-zinc-800 bg-zinc-900/90 text-zinc-300 font-semibold"
              {...props}
            >
              {children}
            </thead>
          ),
          tbody: ({ children, ...props }) => (
            <tbody className="divide-y divide-zinc-800/60" {...props}>
              {children}
            </tbody>
          ),
          tr: ({ children, ...props }) => (
            <tr className="hover:bg-zinc-900/40 transition-colors" {...props}>
              {children}
            </tr>
          ),
          th: ({ children, ...props }) => (
            <th
              className="px-3.5 py-2.5 text-zinc-200 whitespace-nowrap font-medium border-r border-zinc-800/40 last:border-r-0"
              {...props}
            >
              {children}
            </th>
          ),
          td: ({ children, ...props }) => (
            <td
              className="px-3.5 py-2 text-zinc-300 whitespace-nowrap border-r border-zinc-800/30 last:border-r-0"
              {...props}
            >
              {children}
            </td>
          ),
          code: ({ className, children, ...props }) => {
            const isCodeBlock = className?.includes("language-") || String(children).includes("\n");
            if (isCodeBlock) {
              return <CodeBlock className={className}>{children}</CodeBlock>;
            }
            return (
              <code
                className="rounded bg-zinc-800/90 px-1.5 py-0.5 font-mono text-[12px] text-emerald-400 border border-zinc-700/50"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre: ({ children }) => <>{children}</>,
          p: ({ children, ...props }) => (
            <p className="mb-2.5 last:mb-0 leading-relaxed text-zinc-200" {...props}>
              {children}
            </p>
          ),
          ul: ({ children, ...props }) => (
            <ul className="my-2 list-disc pl-5 space-y-1 text-zinc-200" {...props}>
              {children}
            </ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className="my-2 list-decimal pl-5 space-y-1 text-zinc-200" {...props}>
              {children}
            </ol>
          ),
          li: ({ children, ...props }) => (
            <li className="leading-relaxed" {...props}>
              {children}
            </li>
          ),
          strong: ({ children, ...props }) => (
            <strong className="font-semibold text-zinc-100" {...props}>
              {children}
            </strong>
          ),
          blockquote: ({ children, ...props }) => (
            <blockquote
              className="my-2 border-l-2 border-blue-500/80 pl-3 italic text-zinc-400"
              {...props}
            >
              {children}
            </blockquote>
          ),
          a: ({ children, href, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 underline underline-offset-2 hover:text-blue-300 transition-colors"
              {...props}
            >
              {children}
            </a>
          ),
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
}
