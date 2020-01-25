import enum
from transitions import Machine
# import graphviz
# from transitions.extensions import GraphMachine


class Health(object):
    class States(enum.Enum):
        UNKNOWN = 0
        HEALTHY = 1
        DEGRADING = 2
        UNHEALTHY = 3

        def __str__(self):
            return str(self.value)

    def __init__(self, appName, unhealthyThreshold = 2, healthyThreshold = 10, debug=False):
        self.appName = appName
        self.unhealthyChecks = self.healthyChecks = 0
        self.unhealthyThreshold = unhealthyThreshold
        self.healthyThreshold = healthyThreshold

        self.machine = Machine(model=self, states=Health.States, initial=Health.States.UNKNOWN)
        # self.machine = GraphMachine(model=self, use_pygraphviz=False, states=Health.States, initial=Health.States.UNKNOWN)
        self.machine.add_transition(
            trigger='healthyCheck',
            source=[Health.States.UNKNOWN, Health.States.DEGRADING, Health.States.UNHEALTHY],
            dest=Health.States.HEALTHY,
            prepare='incrementHealthy',
            conditions='isHealthThreshold'
        )
        self.machine.add_transition(trigger='healthyCheck', source=[Health.States.HEALTHY], dest=None)

        self.machine.add_transition(
            trigger='unhealthyCheck',
            source=[Health.States.DEGRADING],
            dest=Health.States.UNHEALTHY,
            prepare='incrementUnhealthy',
            conditions='isUnhealthyThreshold'
        )
        self.machine.add_transition(trigger='unhealthyCheck', source=[Health.States.UNHEALTHY], dest=None)

        self.machine.add_transition(
            trigger='unhealthyCheck',
            source=[Health.States.UNKNOWN, Health.States.HEALTHY],
            dest=Health.States.DEGRADING,
            prepare='incrementUnhealthy',
            conditions='isDegrading'
        )

        self.machine.add_transition(trigger='unknown', source=Health.States, dest=Health.States.UNKNOWN)

        # self.machine.get_graph().draw('my_state_diagram.png', prog='dot')

        if debug:
            self.machine.on_enter_UNKNOWN(lambda: print('entering UNKNOWN'))
            self.machine.on_enter_DEGRADING(lambda: print('entering DEGRADING'))
            self.machine.on_enter_UNHEALTHY(lambda: print('entering UNHEALTHY'))
            self.machine.on_enter_HEALTHY(lambda: print('entering HEALTHY'))

    def incrementUnhealthy(self):
        self.healthyChecks = 0
        self.unhealthyChecks += 1 if self.unhealthyChecks < self.unhealthyThreshold else 0

    def incrementHealthy(self):
        self.unhealthyChecks = 0
        self.healthyChecks += 1 if self.healthyChecks < self.healthyThreshold else 0

    def isUnhealthyThreshold(self):
        return self.unhealthyChecks >= self.unhealthyThreshold

    def isDegrading(self):
        return self.unhealthyChecks >= 2

    def isHealthThreshold(self):
        return self.healthyChecks >= self.healthyThreshold


if __name__ == '__main__':
    healthState = Health('test', unhealthyThreshold=4, healthyThreshold=4, debug=True)

    assert healthState.state == Health.States.UNKNOWN

    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    assert healthState.state == Health.States.HEALTHY

    assert healthState.healthyChecks == healthState.healthyThreshold
    assert healthState.unhealthyChecks == 0
    healthState.healthyCheck()
    assert healthState.healthyChecks == healthState.healthyThreshold
    assert healthState.unhealthyChecks == 0

    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.DEGRADING

    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.UNHEALTHY

    assert healthState.unhealthyChecks == healthState.unhealthyThreshold
    assert healthState.healthyChecks == 0
    healthState.unhealthyCheck()
    assert healthState.unhealthyChecks == healthState.unhealthyThreshold
    assert healthState.healthyChecks == 0

    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    assert healthState.state == Health.States.HEALTHY

    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.DEGRADING

    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    assert healthState.state == Health.States.HEALTHY

    healthState.unknown()
    assert healthState.state == Health.States.UNKNOWN

    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.DEGRADING