class InMemoryEventStore:
    def __init__(self):
        self._events=[]

    def append(self,event):
        if any(e.id==event.id for e in self._events):
            raise ValueError("duplicate event id")
        if self._events and event.sequence <= self._events[-1].sequence:
            raise ValueError("sequence must increase")
        self._events.append(event)

    def all(self):
        return list(self._events)

    def up_to(self,sequence):
        return [e for e in self._events if e.sequence<=sequence]
