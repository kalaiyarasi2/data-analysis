import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: ReactNode;
  label: string;
  value: string | number;
  trend?: string;
  variant?: "default" | "primary" | "success" | "warning" | "info";
}

const variantClasses = {
  default: "border-border",
  primary: "border-primary/30",
  success: "border-success/30",
  warning: "border-warning/30",
  info: "border-info/30",
};

const iconVariantClasses = {
  default: "bg-muted text-muted-foreground",
  primary: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  info: "bg-info/10 text-info",
};

export default function StatCard({ icon, label, value, trend, variant = "default" }: StatCardProps) {
  return (
    <div
      className={cn(
        "glass-panel rounded-lg p-5 animate-fade-in",
        variantClasses[variant]
      )}
    >
      <div className="flex items-center gap-4">
        <div className={cn("w-11 h-11 rounded-lg flex items-center justify-center", iconVariantClasses[variant])}>
          {icon}
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-display font-bold text-foreground">{value}</p>
          {trend && <p className="text-xs text-success mt-0.5">{trend}</p>}
        </div>
      </div>
    </div>
  );
}
