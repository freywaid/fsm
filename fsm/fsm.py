"""
Finite State Machine support
"""
import collections


class MissingEvent(KeyError):
    pass


class Table:
    """
    FSM definition table
    """
    def __init__(self, name=None):
        self.name = name or str(id(self))
        self._map = {}
        self._state2events = collections.defaultdict(list)
    def __str__(self):
        return self.name
    def dump(self, indent=0, detailed=False):
        iterable = ( (s,e) for s,events in self._state2events.items() for e in events )
        iterable = ( ((s,e),self._map[(s,e)]) for s,e in iterable )
        return '\n'.join(f'{" "*indent}{FROM} --{event}--> {TO}{":"+str(fn) if detailed else ""}' for
                (FROM,event),(TO,fn) in iterable)
    def upsert(self, transition, fn):
        FROM, event, TO = transition
        self._state2events[FROM].append(event)
        self._map[(FROM, event)] = (TO, fn)
    def __call__(self, FROM, event, TO):
        def _decorator(fn):
            self.upsert((FROM, event, TO), fn)
            return fn
        return _decorator
    def get(self, FROM, event):
        try:
            return self._map[(FROM, event)]
        except KeyError:
            raise MissingEvent(f"No event '{event}' from '{FROM}' state")


class FSM:
    """
    Finite State Machine
    >>> table = Table()
    >>> @table('HELLO', 'event', 'THERE')
    ... def foo(*args, **kwargs):
    ...     pass
    >>> @table('THERE', 'event', 'HELLO')
    ... def bar(*args, **kwargs):
    ...     pass
    >>> fsm = FSM(table, 'HELLO')
    >>> fsm.state
    'HELLO'
    >>> fsm.push('event')
    >>> fsm.push('event')
    >>> for r in fsm.next('stuff'):
    ...     print((fsm.state, r))
    ('THERE', None)
    ('HELLO', None)
    >>> print(fsm.table.dump())
    HELLO --event--> THERE
    THERE --event--> HELLO
    """
    def __init__(self, table, initial, testing=False):
        self._events = collections.deque()
        self.table = table
        self.testing = testing
        self.state = initial
        self.transition = (initial, None, None)     # current transition
    def __str__(self):
        return f'FSM:{self.table} @ {self.state}'
    def dump(self, indent=0, detailed=False):
        return '\n'.join([str(self), self.table.dump(indent=indent+2, detailed=detailed)])
    def _process_event(self, event, *args, **kwargs):
        FROM = self.state
        TO, fn = self.table.get(FROM, event)
        self.transition = transition = (FROM, event, TO)
        if not self.testing:
            r = fn(*args, transition_FSM=transition, **kwargs)
        else:
            r = None
        self.state = TO
        return r
    def push(self, event, **ekwargs):
        self._events.append((event, ekwargs))
    def next(self, *args, **kwargs):
        while self._events:
            old_transition = self.transition
            event, ekwargs = self._events.popleft()
            kwargs.update(ekwargs)
            try:
                yield self._process_event(event, *args, **kwargs)
            except:
                self._events.appendleft((event, ekwargs))
                self.transition = old_transition
                raise
