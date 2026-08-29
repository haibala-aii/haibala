"""
haibala · M5+ · core/events.py
==============================
【这一课：事件总线 + 实时推送（SSE）】
让前端"实时"看到变化（而不只是切页时拉一次）：
  1. 一个内存事件总线：任何地方 publish(事件) -> 广播给所有订阅者。
  2. 后端开一个 Server-Sent Events(SSE) 接口，前端用 EventSource 订阅。
  任务跑完/审批/恢复等都会 publish，前端收到就自动刷新数据。
"""
import queue, threading, json

class EventBus:
    def __init__(self):
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q = queue.Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, event: dict):
        with self._lock:
            for q in list(self._subs):
                try:
                    q.put(event)
                except Exception:
                    pass

bus = EventBus()

def notify(event_type: str, **data):
    bus.publish({"type": event_type, **data})
