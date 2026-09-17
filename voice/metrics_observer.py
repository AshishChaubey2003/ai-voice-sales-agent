from collections import deque
from collections.abc import Callable

from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import TTFBMetricsData
from pipecat.observers.base_observer import BaseObserver, FramePushed


class ServiceTTFBObserver(BaseObserver):
    """Forwards each service TTFB metric once, even though frames pass many hops."""

    def __init__(self, on_ttfb: Callable[[str, float], None], max_remembered: int = 1000) -> None:
        super().__init__()
        self._on_ttfb = on_ttfb
        self._seen_ids: set[int] = set()
        self._seen_order: deque[int] = deque()
        self._max_remembered = max_remembered

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if not isinstance(frame, MetricsFrame) or frame.id in self._seen_ids:
            return
        self._remember(frame.id)
        for item in frame.data:
            if isinstance(item, TTFBMetricsData):
                self._on_ttfb(item.processor, item.value)

    def _remember(self, frame_id: int) -> None:
        self._seen_ids.add(frame_id)
        self._seen_order.append(frame_id)
        if len(self._seen_order) > self._max_remembered:
            self._seen_ids.discard(self._seen_order.popleft())