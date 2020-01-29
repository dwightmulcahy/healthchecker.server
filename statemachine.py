import enum
import logging

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

    def __init__(self, unhealthyThreshold = 2, healthyThreshold = 10, debug = False):
        self.emailAddr = None
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
            conditions='isHealthy'
        )
        self.machine.add_transition(trigger='healthyCheck', source=[Health.States.HEALTHY], dest=None)

        self.machine.add_transition(
            trigger='unhealthyCheck',
            source=[Health.States.DEGRADING],
            dest=Health.States.UNHEALTHY,
            prepare='incrementUnhealthy',
            conditions='isUnhealthy'
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
            # Set transitions' log level to DEBUG, more messages
            logging.getLogger('transitions').setLevel(logging.DEBUG)

            self.machine.on_enter_UNKNOWN(lambda: print('Entering UNKNOWN'))
            self.machine.on_exit_UNKNOWN(lambda: print(f'Exiting UNKNOWN: HC={self.healthyChecks} UHC={self.unhealthyChecks}'))
            self.machine.on_enter_DEGRADING(lambda: print('Entering DEGRADING'))
            self.machine.on_exit_DEGRADING(lambda: print(f'Exiting DEGRADING: HC={self.healthyChecks} UHC={self.unhealthyChecks}'))
            self.machine.on_enter_HEALTHY(lambda: print('Entering HEALTHY'))
            self.machine.on_exit_HEALTHY(lambda: print(f'Exiting HEALTHY: HC={self.healthyChecks} UHC={self.unhealthyChecks}'))
            self.machine.on_enter_UNHEALTHY(lambda: print('Entering UNHEALTHY'))
            self.machine.on_exit_UNHEALTHY(lambda: print(f'Exiting UNHEALTHY: HC={self.healthyChecks} UHC={self.unhealthyChecks}'))
        else:
            # Set transitions' log level to ERROR so only important msgs appear
            logging.getLogger('transitions').setLevel(logging.ERROR)

    def registerEmail(self, appname, emailAddr, emailCallback):
        # set up state on_enters to email callback
        self.machine.on_enter_DEGRADING(
            lambda: emailCallback(
                sendTo=emailAddr,
                messageBody=f"`{appname}` has not responded to the last two health checks.",
                emailSubject=f"`{appname}` health is degraded"
            )
        )
        self.machine.on_enter_HEALTHY(
            lambda: emailCallback(
                sendTo=emailAddr,
                messageBody=f"`{appname}` responded HEALTHY to {self.healthyChecks} health checks.",
                emailSubject=f"`{appname}` is back to healthy"
            )
        )
        self.machine.on_enter_UNHEALTHY(
            lambda: emailCallback(
                sendTo=emailAddr,
                messageBody=f"`{appname}` is UNHEALTHY for last {self.unhealthyChecks} health checks.",
                emailSubject=f"`{appname}` is unhealthy"
            )
        )

    def incrementUnhealthy(self):
        self.unhealthyChecks += 1 if not self.isUnhealthy() else 0
        if self.isUnhealthy():
            self.healthyChecks = 0

    def incrementHealthy(self):
        self.healthyChecks += 1 if not self.isHealthy() else 0
        if self.isHealthy():
            self.unhealthyChecks = 0

    def isUnhealthy(self):
        return self.unhealthyChecks >= self.unhealthyThreshold

    def isDegrading(self):
        return self.unhealthyChecks >= 2

    def isHealthy(self):
        return self.healthyChecks >= self.healthyThreshold


if __name__ == '__main__':
    healthState = Health(unhealthyThreshold=4, healthyThreshold=4, debug=True)

    # initial state machine state
    assert healthState.state == Health.States.UNKNOWN                   #nosec

    # test transition UNKNOWN -> HEALTHY state
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    assert healthState.state == Health.States.HEALTHY                   #nosec

    # make sure the counters are accurate
    assert healthState.healthyChecks == healthState.healthyThreshold    #nosec
    assert healthState.unhealthyChecks == 0                             #nosec

    # counters shouldn't change after getting to threshold
    healthState.healthyCheck()
    assert healthState.healthyChecks == healthState.healthyThreshold    #nosec
    assert healthState.unhealthyChecks == 0                             #nosec

    # test transition HEALTHY -> DEGRADING state
    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.DEGRADING                 #nosec

    # test transition DEGRADING -> UNHEALTHY state
    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.UNHEALTHY                 #nosec

    # counters shouldn't change after getting to threshold
    assert healthState.unhealthyChecks == healthState.unhealthyThreshold    #nosec
    assert healthState.healthyChecks == 0                                   #nosec

    # a single healthy check does not mean a state transition yet
    healthState.healthyCheck()
    assert healthState.unhealthyChecks == healthState.unhealthyThreshold    #nosec
    assert healthState.healthyChecks == 1                                   #nosec

    # test transition UNHEALTHY -> HEALTHY state
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    assert healthState.state == Health.States.HEALTHY                       #nosec

    # test transition HEALTHY -> DEGRADING state
    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.DEGRADING                     #nosec

    # test transition DEGRADING -> HEALTHY state
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    healthState.healthyCheck()
    assert healthState.state == Health.States.HEALTHY                       #nosec

    # test resetting the state to UNKNOWN
    healthState.unknown()
    assert healthState.state == Health.States.UNKNOWN                       #nosec

    # test transition UNKNOWN -> UNHEALTHY state
    healthState.unhealthyCheck()
    healthState.unhealthyCheck()
    assert healthState.state == Health.States.DEGRADING                     #nosec