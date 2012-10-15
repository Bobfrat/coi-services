#!/usr/bin/env python

"""
@package ion.agents.platform.oms.oms_client
@file    ion/agents/platform/oms/oms_client.py
@author  Carlos Rueda
@brief   OmsClient captures the CI-OMS interface.
         See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


class InvalidResponse(object):
    PLATFORM_ID          = 'INVALID-PLATFORM-ID'
    ATTRIBUTE_NAME       = 'INVALID-ATTRIBUTE-NAME'
    ATTRIBUTE_NAME_VALUE = ('INVALID-ATTRIBUTE-NAME', '')
    ATTRIBUTE_NOT_WRITABLE = 'ATTRIBUTE-NOT-WRITABLE'
    PORT_ID              = 'INVALID-PORT-ID'

    PLATFORM_TYPE        = 'INVALID-PLATFORM-TYPE'
    ALARM_LISTENER_URL   = 'INVALID-ALARM-LISTENER-URL'
    ALARM_TYPE           = 'INVALID-ALARM-TYPE'

VALID_PORT_ATTRIBUTES = [
    'maxCurrentDraw', 'initCurrent', 'dataThroughput', 'instrumentType'
]


class OmsClient(object):
    """
    This class captures the interface with OMS.

    See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface

    Note that the real OMS interface uses "handlers" for grouping operations
    (for example, "ping" is actually a method of the "hello" handler). Here we
    define all operations at the base level. As a simple trick to emulate the
    "handler" mechanism, corresponding properties are defined as self.
    """

    @property
    def hello(self):
        return self

    @property
    def config(self):
        return self

    def ping(self):
        """
        Basic verification of connection with OMS.
        """
        raise NotImplemented()

    def getPlatformMap(self):
        """
        Returns platform map. This is the network object model in the OMS.

        @retval [(platform_id, parent_platform_id), ...]
        """
        raise NotImplemented()

    def getRootPlatformID(self):
        """
        Returns the ID of the root platform in the network.
        @retval the ID of the root platform in the network.
        """
        raise NotImplemented()

    def getSubplatformIDs(self, platform_id):
        """
        Returns the IDs of the sub-platforms of the given platform.
        @retval     {platform_id: [sub_platform_id, ...]}
                    Dict with single entry for the desired platform with list
                    of IDs of the corresponding sub-platforms. ||
        """
        raise NotImplemented()

    def getPlatformTypes(self):
        """
        Returns the types of platforms in the network

        @retval { platform_type: description, ... } Dict of platform types in
         the network.
        """
        raise NotImplemented()

    def getPlatformMetadata(self, platform_id):
        """
        Returns the metadata for a requested platform.

        @param platform_id Platform ID
        @retval { platform_id: {mdAttrName: mdAttrValue, ...\, ... }
                dict with a single entry for the requested platform ID with a
                dictionary for corresponding metadata
        """
        raise NotImplemented()

    def getPlatformAttributes(self, platform_id):
        """
        Returns the attributes associated to a given platform.

        @param platform_id Platform ID
        @retval {platform_id: {attrName : info, ...}, ...}
                dict with a single entry for the requested platform ID with an
                info dictionary for each attribute in that platform.
        """
        raise NotImplemented()

    def getPlatformAttributeValues(self, platform_id, attrNames, from_time):
        """
        Returns the values for specific attributes associated with a given
        platform since a given time.

        @param platform_id  Platform ID
        @param attrNames 	[attrName, ...]
                            Names of desired attributes
        @param from_time    NTP v4 compliant string; time from which the values
                            are requested

        @retval {platform_id: {attrName : [(attrValue, timestamp), ...], ...}}
                dict with a single entry for the requested platform ID and value
                as a list of (value,timestamp) pairs for each attribute.
                Returned timestamps are also NTP v4 8-byte strings, or the empty
                string in the cases indicated below.
        """
        raise NotImplemented()

    def setPlatformAttributeValues(self, platform_id, attrs):
        """
        See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
        """
        raise NotImplemented()

    def getPlatformPorts(self, platform_id):
        """
        Returns information for each port in a given platform.

        @param platform_id	 	 Platform ID

        @retval {platform_id: {port_id: portInfo, ...} }
                Dict with information for each port in the platform
        """
        raise NotImplemented()

    def setUpPort(self, platform_id, port_id, attributes):
        """
        Sets up a port in a platform.

        @param platform_id	 	 Platform ID
        @param port_id	 	     PortID ID
        @param attributes	 	 {'maxCurrentDraw': value, 'initCurrent': value,
                                 'dataThroughput': value, 'instrumentType': value}

        @retval TBD
        """
        raise NotImplemented()

    def turnOnPort(self, platform_id, port_id):
        """
        Turns on a port in a platform. The port should have previously set up with setUpPort

        @param platform_id	 	 Platform ID
        @param port_id	 	     PortID ID

        @retval TBD
        """
        raise NotImplemented()

    def turnOffPort(self, platform_id, port_id):
        """
        Turns off a port in a platform.

        @param platform_id	 	 Platform ID
        @param port_id	 	     PortID ID

        @retval TBD
        """
        raise NotImplemented()

    def describeAlarmTypes(self, alarm_type_ids):
        """
        See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
        """
        raise NotImplemented()

    def getAlarmsByPlatformType(self, platform_types):
        """
        See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
        """
        raise NotImplemented()

    def registerAlarmListener(self, url, alarm_types):
        """
        See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
        """
        raise NotImplemented()

    def unregisterAlarmListener(self, url, alarm_types):
        """
        See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
        """
        raise NotImplemented()

    def getRegisteredAlarmListeners(self):
        """
        See https://confluence.oceanobservatories.org/display/CIDev/CI-OMS+interface
        """
        raise NotImplemented()
