# Finite State Machine [ FSM ]

A simple 'pythonic' FSM implementation.  Decorate your actions with state transition.
Create an instance of an FSM using state transition table.  Push events into event queue.
Process state machine using `next` generator.

## State Transition Table

Decorate your actions with state transitions.  Let's say you have a simple two state
machine and one event that can between both states.

```
import fsm

table = fsm.Table()

@table('STATE1', 'doit', 'STATE2')
def action1(*args, **kwargs):
    pass

@table('STATE2', 'doit', 'STATE1')
def action2(*args, **kwargs):
    pass

print(table.dump())
```

OUTPUT
```
STATE1 --doit--> STATE2
STATE2 --doit--> STATE1
```

## FSM Instance

Define an instance of your FSM using the state transition table and an initial state.
To execute your state machine, you `push` events to your event queue and process via the
`next` method.

```
myfsm = fsm.FSM(table, 'STATE1')

myfsm.push('doit')
myfsm.push('doit')

for _ in myfsm.next():
    print(myfsm.state)
```

OUTPUT
```
STATE2
STATE1
```

Since `next` is a generator, you will need to process via generator syntax.  Doing it
this way permits events to be pushed at any point into the FSM.

## Actions

The action `fn` is called for each state transition. Sometimes you'll want to pass annotated
data through the FSM.  The `next` method provides that with `*args, **kwargs`.  You may
push an event with custom `**kwargs` data which will be merged into the action call
`**kwargs`.  Finally, every action called will have an `transition_FSM` passed in as kwargs
as well.

