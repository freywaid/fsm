"""
Unit tests for AsyncFSM.

Driven with ``asyncio.run`` so the suite needs no async pytest plugin.
"""
import asyncio

import pytest

import fsm


def run(coro):
    return asyncio.run(coro)


def _two_state_table(log):
    t = fsm.Table()

    @t('A', 'go', 'B')
    async def a2b(*args, **kwargs):
        log.append(('a2b', args, kwargs))
        return 'a2b'

    @t('B', 'go', 'A')
    async def b2a(*args, **kwargs):
        log.append(('b2a', args, kwargs))
        return 'b2a'

    return t


async def _drain(machine, *args, **kwargs):
    return [r async for r in machine.next(*args, **kwargs)]


def test_async_fsm_is_fsm_subclass():
    assert issubclass(fsm.AsyncFSM, fsm.FSM)


def test_async_processes_events_in_order():
    log = []
    machine = fsm.AsyncFSM(_two_state_table(log), 'A')
    machine.push('go')
    machine.push('go')

    results = run(_drain(machine))

    assert results == ['a2b', 'b2a']
    assert machine.state == 'A'
    assert machine.transition == ('B', 'go', 'A')


def test_async_injects_transition_fsm_kwarg():
    log = []
    machine = fsm.AsyncFSM(_two_state_table(log), 'A')
    machine.push('go')
    run(_drain(machine))

    _, _, kwargs = log[0]
    assert kwargs['transition_FSM'] == ('A', 'go', 'B')


def test_async_passes_args_and_merges_push_kwargs():
    log = []
    machine = fsm.AsyncFSM(_two_state_table(log), 'A')
    machine.push('go', extra='from_push')
    run(_drain(machine, 'pos', shared='from_next'))

    _, args, kwargs = log[0]
    assert args == ('pos',)
    assert kwargs['extra'] == 'from_push'
    assert kwargs['shared'] == 'from_next'


def test_async_testing_mode_skips_action_and_yields_none():
    log = []
    machine = fsm.AsyncFSM(_two_state_table(log), 'A', testing=True)
    machine.push('go')

    results = run(_drain(machine))

    assert results == [None]
    assert log == []
    assert machine.state == 'B'


def test_async_awaits_action_between_yields():
    order = []
    t = fsm.Table()

    @t('A', 'go', 'B')
    async def a2b(*args, **kwargs):
        order.append('start')
        await asyncio.sleep(0)
        order.append('end')
        return 'done'

    machine = fsm.AsyncFSM(t, 'A')
    machine.push('go')

    assert run(_drain(machine)) == ['done']
    assert order == ['start', 'end']


def test_async_accepts_sync_action():
    t = fsm.Table()

    @t('A', 'go', 'B')
    def plain(*args, **kwargs):
        return 'sync'

    machine = fsm.AsyncFSM(t, 'A')
    machine.push('go')

    assert run(_drain(machine)) == ['sync']
    assert machine.state == 'B'


def test_async_mixes_sync_and_async_actions():
    t = fsm.Table()

    @t('A', 'go', 'B')
    def plain(*args, **kwargs):
        return 'sync'

    @t('B', 'go', 'A')
    async def coro(*args, **kwargs):
        await asyncio.sleep(0)
        return 'async'

    machine = fsm.AsyncFSM(t, 'A')
    machine.push('go')
    machine.push('go')

    assert run(_drain(machine)) == ['sync', 'async']
    assert machine.state == 'A'


def test_async_unknown_event_raises_missing_event():
    machine = fsm.AsyncFSM(fsm.Table(), 'A')
    machine.push('nope')
    with pytest.raises(fsm.MissingEvent):
        run(_drain(machine))


def test_async_action_exception_rolls_back_and_requeues():
    t = fsm.Table()

    @t('A', 'boom', 'B')
    async def explode(*args, **kwargs):
        raise ValueError('kaboom')

    machine = fsm.AsyncFSM(t, 'A')
    machine.push('boom')

    with pytest.raises(ValueError):
        run(_drain(machine))

    # state unchanged and event preserved for a retry
    assert machine.state == 'A'
    assert machine.transition == ('A', None, None)

    @t('A', 'boom', 'B')
    async def ok(*args, **kwargs):
        return 'recovered'

    assert run(_drain(machine)) == ['recovered']
    assert machine.state == 'B'
