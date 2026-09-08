import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";

export default function HomeGoalStrategyCard({ number, title, children }: {
  number: number; title: string; children: ReactNode;
}) {
  return (
    <Card className="min-w-0 gap-3 p-4">
      <div className="flex items-center gap-2">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-xs font-extrabold text-brand-dark">{number}</span>
        <h4 className="text-sm font-bold">{title}</h4>
      </div>
      {children}
    </Card>
  );
}
