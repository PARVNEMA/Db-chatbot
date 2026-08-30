"use client";

import * as React from "react";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface SelectOption {
  value: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}

interface SelectProps {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function Select({
  value: controlledValue,
  defaultValue,
  onValueChange,
  options,
  placeholder = "Select an option",
  disabled = false,
  className,
}: SelectProps): React.JSX.Element {
  const [uncontrolledValue, setUncontrolledValue] = React.useState(
    defaultValue || ""
  );
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const isControlled = controlledValue !== undefined;
  const currentValue = isControlled ? controlledValue : uncontrolledValue;

  const selectedOption = options.find((opt) => opt.value === currentValue);

  const handleSelect = (val: string) => {
    if (!isControlled) {
      setUncontrolledValue(val);
    }
    onValueChange?.(val);
    setOpen(false);
  };

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={cn(
          "flex h-9 w-full items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50 transition-colors text-left",
          !selectedOption && "text-zinc-500"
        )}
      >
        <span className="flex items-center gap-2 truncate">
          {selectedOption ? (
            <>
              {selectedOption.icon}
              <span className="text-zinc-100">{selectedOption.label}</span>
            </>
          ) : (
            placeholder
          )}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-zinc-400 opacity-70" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-xl border border-zinc-800 bg-zinc-900/95 p-1 text-zinc-100 shadow-2xl backdrop-blur-md animate-in fade-in-0 zoom-in-95">
          {options.map((option) => {
            const isSelected = option.value === currentValue;
            return (
              <div
                key={option.value}
                onClick={() => handleSelect(option.value)}
                className={cn(
                  "relative flex cursor-pointer select-none items-center justify-between rounded-lg px-3 py-2 text-xs outline-none transition-colors hover:bg-zinc-800 hover:text-white",
                  isSelected && "bg-blue-600/15 text-blue-400 font-semibold"
                )}
              >
                <div className="flex items-center gap-2">
                  {option.icon}
                  <div>
                    <div>{option.label}</div>
                    {option.description && (
                      <div className="text-[10px] text-zinc-500 font-normal">
                        {option.description}
                      </div>
                    )}
                  </div>
                </div>
                {isSelected && <Check className="h-3.5 w-3.5 text-blue-400" />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
