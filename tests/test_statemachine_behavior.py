"""State-machine transition, counter, notification, and debug regressions."""

from unittest.mock import MagicMock
import logging

import pytest

from statemachine import Health


def test_healthy_degrading_unhealthy_and_recovery():
    state = Health(unhealthyThreshold=4, healthyThreshold=4)
    assert state.state == Health.States.UNKNOWN
    for _ in range(3):
        state.healthyCheck()
        assert state.state == Health.States.UNKNOWN
    state.healthyCheck()
    assert state.state == Health.States.HEALTHY
    assert state.healthyChecks == 4
    assert state.unhealthyChecks == 0
    state.healthyCheck()
    assert state.healthyChecks == 4

    state.unhealthyCheck()
    state.unhealthyCheck()
    assert state.state == Health.States.DEGRADING
    state.unhealthyCheck()
    state.unhealthyCheck()
    assert state.state == Health.States.UNHEALTHY
    assert state.unhealthyChecks == 4
    state.unhealthyCheck()
    assert state.unhealthyChecks == 4

    for _ in range(3):
        state.healthyCheck()
        assert state.state == Health.States.UNHEALTHY
    state.healthyCheck()
    assert state.state == Health.States.HEALTHY
    assert state.unhealthyChecks == 0
    state.unknown()
    assert state.state == Health.States.UNKNOWN


def test_degraded_state_can_recover_without_becoming_unhealthy():
    state = Health(unhealthyThreshold=3, healthyThreshold=2)
    state.unhealthyCheck()
    state.unhealthyCheck()
    assert state.state == Health.States.DEGRADING
    state.healthyCheck()
    state.healthyCheck()
    assert state.state == Health.States.HEALTHY
    assert state.unhealthyChecks == 0


def test_notifications_are_fired_on_transitions_only():
    callback = MagicMock()
    state = Health(unhealthyThreshold=3, healthyThreshold=2)
    state.registerEmail("backend", "admin@example.org", callback)
    assert state.emailAddr == "admin@example.org"
    state.unhealthyCheck()
    state.unhealthyCheck()
    assert "degraded" in callback.call_args.kwargs["emailSubject"]
    state.unhealthyCheck()
    assert "unhealthy" in callback.call_args.kwargs["emailSubject"]
    state.healthyCheck()
    state.healthyCheck()
    assert "back to healthy" in callback.call_args.kwargs["emailSubject"]
    assert callback.call_count == 3
    assert all(call.kwargs["sendTo"] == "admin@example.org" for call in callback.call_args_list)


def test_counter_thresholds_and_state_helpers():
    state = Health(unhealthyThreshold=2, healthyThreshold=2)
    assert not state.isHealthy()
    assert not state.isDegrading()
    assert not state.isUnhealthy()
    state.incrementUnhealthy()
    assert state.unhealthyChecks == 1
    state.incrementUnhealthy()
    assert state.isUnhealthy()
    assert state.isDegrading()
    state.incrementUnhealthy()
    assert state.unhealthyChecks == 2
    assert state.healthyChecks == 0
    state.incrementHealthy()
    state.incrementHealthy()
    assert state.isHealthy()
    assert state.unhealthyChecks == 0
    state.incrementHealthy()
    assert state.healthyChecks == 2


def test_debug_mode_registers_logging_callbacks(capsys):
    state = Health(unhealthyThreshold=2, healthyThreshold=2, debug=True)
    state.healthyCheck()
    state.healthyCheck()
    assert state.state == Health.States.HEALTHY
    assert "Entering HEALTHY" in capsys.readouterr().out
    assert logging.getLogger("transitions").level == logging.DEBUG


def test_state_enum_string_values():
    assert str(Health.States.UNKNOWN) == "0"
    assert str(Health.States.HEALTHY) == "1"
