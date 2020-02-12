"""Test zha lock."""
from unittest.mock import patch

import pytest
import zigpy.profiles.zha
import zigpy.zcl.clusters.closures as closures
import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.lock import DOMAIN
from homeassistant.const import STATE_LOCKED, STATE_UNAVAILABLE, STATE_UNLOCKED

from .common import (
    async_enable_traffic,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

from tests.common import mock_coro

LOCK_DOOR = 0
UNLOCK_DOOR = 1


@pytest.fixture(params=["zha_device_joined", "zha_device_restored"])
async def lock(hass, zha_gateway, zigpy_device_mock, request):
    """Lock cluster fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [closures.DoorLock.cluster_id, general.Basic.cluster_id],
                "out_clusters": [],
                "device_type": zigpy.profiles.zha.DeviceType.DOOR_LOCK,
            }
        },
    )

    join_or_restore = request.getfixturevalue(request.param)
    zha_device = await join_or_restore(zigpy_device)
    return zha_device, zigpy_device.endpoints[1].door_lock


async def test_lock(hass, zha_gateway, lock):
    """Test zha lock platform."""

    zha_device, cluster = lock
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the lock was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    # test that the state has changed from unavailable to unlocked
    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    # set state to locked
    attr = make_attribute(0, 1)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_LOCKED

    # set state to unlocked
    attr.value.value = 2
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    # lock from HA
    await async_lock(hass, cluster, entity_id)

    # unlock from HA
    await async_unlock(hass, cluster, entity_id)


async def async_lock(hass, cluster, entity_id):
    """Test lock functionality from hass."""
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([zcl_f.Status.SUCCESS])
    ):
        # lock via UI
        await hass.services.async_call(
            DOMAIN, "lock", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == LOCK_DOOR


async def async_unlock(hass, cluster, entity_id):
    """Test lock functionality from hass."""
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([zcl_f.Status.SUCCESS])
    ):
        # lock via UI
        await hass.services.async_call(
            DOMAIN, "unlock", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == UNLOCK_DOOR
