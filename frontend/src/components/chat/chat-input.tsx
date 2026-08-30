"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Square, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatInputProps {
  onSendMessage: (content: string) => void;
  onStopStream?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  suggestions?: string[];
}

export function ChatInput({
  onSendMessage,
  onStopStream,
  isStreaming = false,
  disabled = false,
  suggestions = [
    "Show top 5 customers by total order revenue",
    "List users registered in the last 30 days",
    "What is the average transaction amount by status?",
    "Count orders grouped by delivery state",
  ],
}: ChatInputProps): React.JSX.Element {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!content.trim() || isStreaming || disabled) return;
    onSendMessage(content.trim());
    setContent("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    if (!isStreaming) {
      textareaRef.current?.focus();
    }
  }, [isStreaming]);

  return (
    <div className="space-y-3">
      {/* Quick Prompt Suggestion Pills */}
      {!isStreaming && (
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
          <span className="text-[11px] font-mono text-zinc-500 shrink-0 flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-blue-400" /> Suggestions:
          </span>
          {suggestions.map((prompt, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onSendMessage(prompt)}
              disabled={disabled}
              className="px-2.5 py-1 rounded-lg bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800/80 text-zinc-400 hover:text-zinc-200 transition-colors text-[11px] font-mono whitespace-nowrap shrink-0"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input Box */}
      <form
        onSubmit={handleSubmit}
        className="relative rounded-2xl border border-zinc-800 bg-zinc-900/90 shadow-2xl p-2 focus-within:border-blue-500/60 focus-within:ring-1 focus-within:ring-blue-500/30 transition-all"
      >
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your database in natural language (e.g. 'Show top 10 orders')..."
          rows={2}
          disabled={disabled || isStreaming}
          className="min-h-[56px] max-h-32 border-0 bg-transparent px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-0 resize-none font-sans"
        />

        <div className="flex items-center justify-between pt-1 px-2 text-xs text-zinc-500">
          <div className="flex items-center gap-1 text-[11px] font-mono">
            <span>Press</span>
            <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 text-[10px]">
              Enter ↵
            </kbd>
            <span>to send,</span>
            <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 text-[10px]">
              Shift + Enter
            </kbd>
            <span>for newline</span>
          </div>

          {isStreaming ? (
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={onStopStream}
              className="h-8 px-3 bg-red-600 hover:bg-red-500 text-white text-xs gap-1.5"
            >
              <Square className="h-3.5 w-3.5" />
              Stop Agent
            </Button>
          ) : (
            <Button
              type="submit"
              size="sm"
              disabled={!content.trim() || disabled}
              className="h-8 px-3.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium gap-1.5 shadow-md shadow-blue-600/20 disabled:opacity-40"
            >
              <span>Send Query</span>
              <Send className="h-3 w-3" />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
