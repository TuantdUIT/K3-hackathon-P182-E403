import { MousePointer2, TextCursorInput } from 'lucide-react';

/**
 * Con trỏ ảo — điểm nhấn của demo.
 *
 * Overlay `fixed` + `pointer-events-none` để không bao giờ chặn chuột thật của
 * khách. z-200 nằm trên cả modal (z-100) và chat popup (z-120).
 * Việc di chuyển do `transition transform 500ms` lo, khớp với `sleep(500)` trong
 * `move_to()` — cursor tới đích rồi mới bắt đầu gõ.
 */
export default function AgentCursor({ cursor }) {
  if (!cursor?.visible) return null;

  const Icon = cursor.typing ? TextCursorInput : MousePointer2;

  return (
    <div
      className="pointer-events-none fixed left-0 top-0 z-200 transition-transform duration-500 ease-out"
      style={{ transform: `translate3d(${cursor.x}px, ${cursor.y}px, 0)` }}
      aria-hidden="true"
    >
      <div className="relative">
        {cursor.clicking && (
          <span className="absolute -left-3 -top-3 h-10 w-10 animate-ping rounded-full bg-brand-500/40" />
        )}

        <span className="relative grid h-8 w-8 place-items-center rounded-full bg-brand-600 shadow-lift ring-2 ring-white">
          <Icon className="h-4 w-4 text-white" />
        </span>

        {cursor.label && (
          <span className="absolute left-9 top-1 whitespace-nowrap rounded-lg bg-ink-900 px-2.5 py-1 text-xs font-semibold text-white shadow-lift">
            {cursor.label}
          </span>
        )}
      </div>
    </div>
  );
}
