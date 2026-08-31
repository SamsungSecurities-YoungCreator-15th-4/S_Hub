import { FileChartColumn } from "lucide-react";
import { Button } from "@/components/ui/button";

const symphonyUrl =
  process.env.NEXT_PUBLIC_SYMPHONY_URL || "https://s-ymphony.streamlit.app/";

/** S.ymphony 리스크 리포트를 별도 탭에서 연다. */
export default function SymphonyLaunchButton() {
  return (
    <Button
      asChild
      variant="outline"
      className="shrink-0 border border-blue-200 bg-blue-50 font-bold text-blue-700 shadow-none hover:bg-blue-100 hover:text-blue-800"
    >
      <a
        href={symphonyUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="S.ymphony 리스크 리포트 새 탭에서 열기"
        title="S.ymphony 리스크 리포트 새 탭에서 열기"
      >
        <FileChartColumn className="size-4" />
        <span className="hidden lg:inline">리스크 리포트</span>
      </a>
    </Button>
  );
}
