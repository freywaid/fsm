"""
Unit tests for the fsm package.
"""
import pytest

import fsm


# --------------------------------------------------------------------------- #
# Table
# --------------------------------------------------------------------------- #
def test_table_default_name_is_stable_id():
    t = fsm.Table()
    assert str(t) == t.name
    assert t.name  # non-empty


def test_table_explicit_name():
    t = fsm.Table('mytable')
    assert t.name == 'mytable'
    assert str(t) == 'mytable'


def test_table_decorator_registers_and_returns_fn():
    t = fsm.Table()

    @t('A', 'go', 'B')
    def action():
        return 'called'

    # decorator returns the original function untouched
    assert action() == 'called'
    assert t.get('A', 'go') == ('B', action)


def test_table_upsert_overwrites_target():
    t = fsm.Table()

    @t('A', 'go', 'B')
    def first():
        pass

    @t('A', 'go', 'C')
    def second():
        pass

    to, fn = t.get('A', 'go')
    assert to == 'C'
    assert fn is second


def test_table_get_missing_raises_missing_event():
    t = fsm.Table()
    with pytest.raises(fsm.MissingEvent):
        t.get('NOPE', 'event')


def test_missing_event_is_keyerror_subclass():
    assert issubclass(fsm.MissingEvent, KeyError)


def test_table_dump():
    t = fsm.Table()

    @t('A', 'go', 'B')
    def f():
        pass

    assert t.dump() == 'A --go--> B'


def test_table_dump_indent_and_detailed():
    t = fsm.Table()

    @t('A', 'go', 'B')
    def named():
        pass

    out = t.dump(indent=2, detailed=True)
    assert out.startswith('  A --go--> B:')
    assert 'named' in out


# --------------------------------------------------------------------------- #
# FSM
# --------------------------------------------------------------------------- #
def _two_state_table(log):
    t = fsm.Table()

    @t('A', 'go', 'B')
    def a2b(*args, **kwargs):
        log.append(('a2b', args, kwargs))
        return 'a2b'

    @t('B', 'go', 'A')
    def b2a(*args, **kwargs):
        log.append(('b2a', args, kwargs))
        return 'b2a'

    return t


def test_fsm_initial_state_and_transition():
    machine = fsm.FSM(fsm.Table(), 'A')
    assert machine.state == 'A'
    assert machine.transition == ('A', None, None)


def test_fsm_str():
    t = fsm.Table('tbl')
    machine = fsm.FSM(t, 'A')
    assert str(machine) == 'FSM:tbl @ A'


def test_fsm_processes_queued_events_in_order():
    log = []
    machine = fsm.FSM(_two_state_table(log), 'A')
    machine.push('go')
    machine.push('go')

    results = list(machine.next())

    assert results == ['a2b', 'b2a']
    assert machine.state == 'A'
    assert machine.transition == ('B', 'go', 'A')


def test_fsm_next_is_lazy_generator():
    log = []
    machine = fsm.FSM(_two_state_table(log), 'A')
    machine.push('go')

    gen = machine.next()
    assert log == []          # nothing processed until iterated
    next(gen)
    assert log and log[0][0] == 'a2b'


def test_fsm_injects_transition_fsm_kwarg():
    log = []
    machine = fsm.FSM(_two_state_table(log), 'A')
    machine.push('go')
    list(machine.next())

    _, _, kwargs = log[0]
    assert kwargs['transition_FSM'] == ('A', 'go', 'B')


def test_fsm_passes_through_args_and_kwargs():
    log = []
    machine = fsm.FSM(_two_state_table(log), 'A')
    machine.push('go')
    list(machine.next('pos', shared='x'))

    _, args, kwargs = log[0]
    assert args == ('pos',)
    assert kwargs['shared'] == 'x'


def test_fsm_push_ekwargs_merge_into_action():
    log = []
    machine = fsm.FSM(_two_state_table(log), 'A')
    machine.push('go', extra='from_push')
    list(machine.next(shared='from_next'))

    _, _, kwargs = log[0]
    assert kwargs['extra'] == 'from_push'
    assert kwargs['shared'] == 'from_next'


def test_fsm_testing_mode_skips_action_and_yields_none():
    log = []
    machine = fsm.FSM(_two_state_table(log), 'A', testing=True)
    machine.push('go')

    results = list(machine.next())

    assert results == [None]      # fn not invoked, returns None
    assert log == []
    assert machine.state == 'B'   # transition still happens


def test_fsm_unknown_event_raises_missing_event():
    machine = fsm.FSM(fsm.Table(), 'A')
    machine.push('nope')
    with pytest.raises(fsm.MissingEvent):
        list(machine.next())


def test_fsm_action_exception_rolls_back_and_requeues():
    t = fsm.Table()

    @t('A', 'boom', 'B')
    def explode(*args, **kwargs):
        raise ValueError('kaboom')

    machine = fsm.FSM(t, 'A')
    machine.push('boom')

    with pytest.raises(ValueError):
        list(machine.next())

    # state unchanged and event preserved for a retry
    assert machine.state == 'A'
    assert machine.transition == ('A', None, None)

    # re-pushing the missing transition lets it run; prove the event is still queued
    @t('A', 'boom', 'B')
    def ok(*args, **kwargs):
        return 'recovered'

    assert list(machine.next()) == ['recovered']
    assert machine.state == 'B'
