import React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padding?: "sm" | "md" | "lg";
}

export function Card({ padding = "md", className = "", children, ...rest }: CardProps) {
  const pad = { sm: "p-3", md: "p-4", lg: "p-5" }[padding];
  return (
    <div className={`haqli-card ${pad} ${className}`} {...rest}>
      {children}
    </div>
  );
}
