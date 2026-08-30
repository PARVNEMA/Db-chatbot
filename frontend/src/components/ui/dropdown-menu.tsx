"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface DropdownContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const DropdownContext = React.createContext<DropdownContextType | undefined>(
  undefined
);

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node)
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
    <DropdownContext.Provider value={{ open, setOpen }}>
      <div ref={menuRef} className="relative inline-block text-left">
        {children}
      </div>
    </DropdownContext.Provider>
  );
}

export function DropdownMenuTrigger({
  children,
  className,
  asChild,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) {
  const context = React.useContext(DropdownContext);
  if (!context) {
    throw new Error("DropdownMenuTrigger must be used within DropdownMenu");
  }

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    props.onClick?.(e);
    context.setOpen(!context.open);
  };

  if (asChild && React.isValidElement(children)) {
    const childProps = children.props as { onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void };
    return React.cloneElement(children, {
      ...childProps,
      onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
        childProps.onClick?.(e);
        context.setOpen(!context.open);
      },
    } as React.Attributes);
  }

  return (
    <button
      type="button"
      className={className}
      onClick={handleClick}
      {...props}
    >
      {children}
    </button>
  );
}

export function DropdownMenuContent({
  children,
  className,
  align = "end",
}: {
  children: React.ReactNode;
  className?: string;
  align?: "start" | "end" | "center";
}) {
  const context = React.useContext(DropdownContext);
  if (!context) {
    throw new Error("DropdownMenuContent must be used within DropdownMenu");
  }

  if (!context.open) return null;

  return (
    <div
      className={cn(
        "absolute z-50 mt-2 min-w-[12rem] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/95 p-1 text-zinc-100 shadow-2xl backdrop-blur-md animate-in fade-in-0 zoom-in-95",
        align === "end" && "right-0",
        align === "start" && "left-0",
        align === "center" && "left-1/2 -translate-x-1/2",
        className
      )}
    >
      {children}
    </div>
  );
}

export function DropdownMenuItem({
  children,
  className,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  const context = React.useContext(DropdownContext);

  const handleClick = () => {
    if (disabled) return;
    onClick?.();
    context?.setOpen(false);
  };

  return (
    <div
      onClick={handleClick}
      className={cn(
        "relative flex cursor-pointer select-none items-center rounded-lg px-2.5 py-1.5 text-xs outline-none transition-colors hover:bg-zinc-800/80 hover:text-white focus:bg-zinc-800 focus:text-white data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        disabled && "opacity-50 pointer-events-none cursor-not-allowed",
        className
      )}
    >
      {children}
    </div>
  );
}

export function DropdownMenuLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "px-2.5 py-1.5 text-[11px] font-semibold text-zinc-400 font-mono",
        className
      )}
    >
      {children}
    </div>
  );
}

export function DropdownMenuSeparator({
  className,
}: {
  className?: string;
}) {
  return <div className={cn("-mx-1 my-1 h-px bg-zinc-800", className)} />;
}
