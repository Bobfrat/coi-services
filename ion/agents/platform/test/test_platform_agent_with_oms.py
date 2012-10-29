#!/usr/bin/env python

"""
@package ion.agents.platform.test.test_platform_agent_with_oms
@file    ion/agents/platform/test/test_platform_agent_with_oms.py
@author  Carlos Rueda
@brief   Test cases for R2 platform agent interacting with OMS
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


from pyon.public import log

from pyon.core.exception import ServerError
from pyon.util.context import LocalContextMixin

from pyon.agent.agent import ResourceAgentClient
from interface.objects import AgentCommand
from interface.objects import CapabilityType
from interface.objects import AgentCapability

from pyon.util.int_test import IonIntegrationTestCase
from ion.agents.platform.platform_agent import PlatformAgentState
from ion.agents.platform.platform_agent import PlatformAgentEvent
from ion.agents.platform.platform_agent_launcher import LauncherFactory

from ion.agents.platform.test.helper import PLATFORM_ID
from ion.agents.platform.test.helper import SUBPLATFORM_IDS
from ion.agents.platform.test.helper import ATTR_NAMES
from ion.agents.platform.test.helper import WRITABLE_ATTR_NAMES
from ion.agents.platform.test.helper import VALID_ATTR_VALUE
from ion.agents.platform.test.helper import INVALID_ATTR_VALUE
from ion.agents.platform.test.helper import HelperTestMixin

from pyon.ion.stream import StandaloneStreamSubscriber
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient

from ion.agents.platform.test.adhoc import adhoc_get_parameter_dictionary
from ion.agents.platform.test.adhoc import adhoc_get_stream_names

from gevent.event import AsyncResult
from gevent import sleep

import time
import unittest
import os
from nose.plugins.attrib import attr


# TIMEOUT: timeout for each execute_agent call.
# NOTE: the bigger the platform network size starting from the chosen
# PLATFORM_ID above, the more the time that should be given for commands to
# complete, in particular, for those with a cascading effect on all the
# descendents, eg, INITIALIZE. In the current network.yml there are 19
# descendent platforms from 'Node1A' taking around 25secs for the INITIALIZE
# command to complete on my local env (this elapsed time reduces to ~14secs
# when using --with-pycc).
# The following TIMEOUT value intends to be big enough for all typical cases.
TIMEOUT = 90


DVR_CONFIG = {
    'dvr_mod': 'ion.agents.platform.oms.oms_platform_driver',
    'dvr_cls': 'OmsPlatformDriver',
    'oms_uri': 'embsimulator',
}

PLATFORM_CONFIG = {
    'platform_id': PLATFORM_ID,
    'driver_config': DVR_CONFIG,
    'container_name': None,  # determined in setUp
}

# Agent parameters.
PA_RESOURCE_ID = 'platform_agent_001'
PA_NAME = 'PlatformAgent001'
PA_MOD = 'ion.agents.platform.platform_agent'
PA_CLS = 'PlatformAgent'


class FakeProcess(LocalContextMixin):
    """
    A fake process used because the test case is not an ion process.
    """
    name = ''
    id=''
    process_type = ''


@attr('INT', group='sa')
class TestPlatformAgent(IonIntegrationTestCase, HelperTestMixin):

    def setUp(self):

        self._start_container()
        self.container.start_rel_from_url('res/deploy/r2deploy.yml')

        self._pubsub_client = PubsubManagementServiceClient(node=self.container.node)

        PLATFORM_CONFIG['container_name'] = self.container.name

        # Start data suscribers, add stop to cleanup.
        # Define stream_config.
        self._async_data_result = AsyncResult()
        self._data_greenlets = []
        self._stream_config = {}
        self._samples_received = []
        self._data_subscribers = []
        self._start_data_subscribers()
        self.addCleanup(self._stop_data_subscribers)

        self._agent_config = {
            'agent'         : {'resource_id': PA_RESOURCE_ID},
            'stream_config' : self._stream_config,
            'test_mode' : True
        }

        log.debug("launching with agent_config=%s",  str(self._agent_config))


        if os.getenv("STANDALONE") is not None:
            standalone = {
                'platform_id': PLATFORM_ID,
                'container': self.container,
                'pubsub_client': self._pubsub_client
            }
            self._launcher = LauncherFactory.createLauncher(standalone=standalone)
            self._pid = self._launcher.launch(PLATFORM_ID, self._agent_config)
            self._pa_client = self._pid

            log.debug("STANDALONE: LAUNCHED PLATFORM_ID=%r", PLATFORM_ID)

        else:
            self._launcher = LauncherFactory.createLauncher()
            self._pid = self._launcher.launch(PLATFORM_ID, self._agent_config)

            log.debug("LAUNCHED PLATFORM_ID=%r", PLATFORM_ID)

            # Start a resource agent client to talk with the agent.
            self._pa_client = ResourceAgentClient(PA_RESOURCE_ID, process=FakeProcess())
            log.info('Got pa client %s.' % str(self._pa_client))

    def tearDown(self):
        try:
            self._launcher.cancel_process(self._pid)
        finally:
            super(TestPlatformAgent, self).tearDown()

    def _start_data_subscribers(self):
        """
        """

        # Create streams and subscriptions for each stream named in driver.
        self._stream_config = {}
        self._data_subscribers = []

        #
        # TODO retrieve appropriate stream definitions; for the moment, using
        # adhoc_get_stream_names
        #

        # A callback for processing subscribed-to data.
        def consume_data(message, stream_route, stream_id):
            log.info('Subscriber received data message: %s.' % str(message))
            self._samples_received.append(message)
            self._async_data_result.set()

        for stream_name in adhoc_get_stream_names():
            log.info('creating stream %r ...', stream_name)

            # TODO use appropriate exchange_point
            stream_id, stream_route = self._pubsub_client.create_stream(
                name=stream_name, exchange_point='science_data')

            log.info('create_stream(%r): stream_id=%r, stream_route=%s',
                     stream_name, stream_id, str(stream_route))

            pdict = adhoc_get_parameter_dictionary(stream_name)
            stream_config = dict(stream_route=stream_route.routing_key,
                                 stream_id=stream_id,
                                 parameter_dictionary=pdict.dump())

            self._stream_config[stream_name] = stream_config
            log.info('_stream_config[%r]= %r', stream_name, stream_config)

            # Create subscriptions for each stream.
            exchange_name = '%s_queue' % stream_name
            self._purge_queue(exchange_name)
            sub = StandaloneStreamSubscriber(exchange_name, consume_data)
            sub.start()
            self._data_subscribers.append(sub)
            sub_id = self._pubsub_client.create_subscription(name=exchange_name, stream_ids=[stream_id])
            self._pubsub_client.activate_subscription(sub_id)
            sub.subscription_id = sub_id

    def _purge_queue(self, queue):
        xn = self.container.ex_manager.create_xn_queue(queue)
        xn.purge()

    def _stop_data_subscribers(self):
        """
        Stop the data subscribers on cleanup.
        """
        for sub in self._data_subscribers:
            if hasattr(sub, 'subscription_id'):
                try:
                    self._pubsub_client.deactivate_subscription(sub.subscription_id)
                except:
                    pass
                self._pubsub_client.delete_subscription(sub.subscription_id)
            sub.stop()

    def _get_state(self):
        state = self._pa_client.get_agent_state()
        return state

    def _assert_state(self, state):
        self.assertEquals(self._get_state(), state)

    def _execute_agent(self, cmd, timeout=TIMEOUT):
        log.info("_execute_agent: cmd=%r ...", cmd.command)
        time_start = time.time()
        retval = self._pa_client.execute_agent(cmd, timeout=timeout)
        elapsed_time = time.time() - time_start
        log.info("_execute_agent: cmd=%r elapsed_time=%s, retval = %s",
                 cmd.command, elapsed_time, str(retval))
        return retval

    def _reset(self):
        cmd = AgentCommand(command=PlatformAgentEvent.RESET)
        retval = self._execute_agent(cmd)
        self._assert_state(PlatformAgentState.UNINITIALIZED)

    def _ping_agent(self):
        retval = self._pa_client.ping_agent()
        self.assertIsInstance(retval, str)

    def _ping_resource(self):
        cmd = AgentCommand(command=PlatformAgentEvent.PING_RESOURCE)
        if self._get_state() == PlatformAgentState.UNINITIALIZED:
            # should get ServerError: "Command not handled in current state"
            with self.assertRaises(ServerError):
                self._pa_client.execute_agent(cmd, timeout=TIMEOUT)
        else:
            # In all other states the command should be accepted:
            retval = self._execute_agent(cmd)
            self.assertEquals("PONG", retval.result)

    def _get_resource(self):
        kwargs = dict(attr_names=ATTR_NAMES, from_time=time.time())
        cmd = AgentCommand(command=PlatformAgentEvent.GET_RESOURCE, kwargs=kwargs)
        retval = self._execute_agent(cmd)
        attr_values = retval.result
        self.assertIsInstance(attr_values, dict)
        for attr_name in ATTR_NAMES:
            self._verify_valid_attribute_id(attr_name, attr_values)

    def _set_resource(self):
        attrNames = ATTR_NAMES

        # TODO more realistic value depending on attribute's type
        attrs = [(attrName, VALID_ATTR_VALUE) for attrName in attrNames]
        kwargs = dict(attrs=attrs)
        cmd = AgentCommand(command=PlatformAgentEvent.SET_RESOURCE, kwargs=kwargs)
        retval = self._execute_agent(cmd)
        attr_values = retval.result
        self.assertIsInstance(attr_values, dict)
        for attrName in attrNames:
            if attrName in WRITABLE_ATTR_NAMES:
                self._verify_valid_attribute_id(attrName, attr_values)
            else:
                self._verify_not_writable_attribute_id(attrName, attr_values)

        # now test setting invalid values to writable attributes:
        attrs = [(attrName, INVALID_ATTR_VALUE) for attrName in WRITABLE_ATTR_NAMES]
        kwargs = dict(attrs=attrs)
        cmd = AgentCommand(command=PlatformAgentEvent.SET_RESOURCE, kwargs=kwargs)
        retval = self._execute_agent(cmd)
        attr_values = retval.result
        self.assertIsInstance(attr_values, dict)
        for attrName in WRITABLE_ATTR_NAMES:
            self._verify_invalid_attribute_id(attrName, attr_values)

    def _initialize(self):
        kwargs = dict(plat_config=PLATFORM_CONFIG)
        self._assert_state(PlatformAgentState.UNINITIALIZED)
        cmd = AgentCommand(command=PlatformAgentEvent.INITIALIZE, kwargs=kwargs)
        retval = self._execute_agent(cmd)
        self._assert_state(PlatformAgentState.INACTIVE)

    def _go_active(self):
        cmd = AgentCommand(command=PlatformAgentEvent.GO_ACTIVE)
        retval = self._execute_agent(cmd)
        self._assert_state(PlatformAgentState.IDLE)

    def _run(self):
        cmd = AgentCommand(command=PlatformAgentEvent.RUN)
        retval = self._execute_agent(cmd)
        self._assert_state(PlatformAgentState.COMMAND)

    def _go_inactive(self):
        cmd = AgentCommand(command=PlatformAgentEvent.GO_INACTIVE)
        retval = self._execute_agent(cmd)
        self._assert_state(PlatformAgentState.INACTIVE)

    def _get_subplatform_ids(self):
        cmd = AgentCommand(command=PlatformAgentEvent.GET_SUBPLATFORM_IDS)
        retval = self._execute_agent(cmd)
        self.assertIsInstance(retval.result, list)
        self.assertTrue(x in retval.result for x in SUBPLATFORM_IDS)
        return retval.result

    def _start_alarm_dispatch(self):
        kwargs = dict(params="TODO set params")
        cmd = AgentCommand(command=PlatformAgentEvent.START_ALARM_DISPATCH, kwargs=kwargs)
        retval = self._execute_agent(cmd)
        self.assertTrue(retval.result is not None)
        return retval.result

    def _wait_for_a_data_sample(self):
        log.info("waiting for reception of a data sample...")
        self._async_data_result.get(timeout=15)
        # we just wait for one -- see consume_data above
        self.assertEquals(len(self._samples_received), 1)

    def _stop_alarm_dispatch(self):
        cmd = AgentCommand(command=PlatformAgentEvent.STOP_ALARM_DISPATCH)
        retval = self._execute_agent(cmd)
        self.assertTrue(retval.result is not None)
        return retval.result

    def test_capabilities(self):

        log.info("test_capabilities starting.  Default timeout=%s", TIMEOUT)

        agt_cmds_all = [
            PlatformAgentEvent.INITIALIZE,
            PlatformAgentEvent.RESET,
            PlatformAgentEvent.GO_ACTIVE,
            PlatformAgentEvent.GO_INACTIVE,
            PlatformAgentEvent.RUN,
            PlatformAgentEvent.GET_RESOURCE_CAPABILITIES,
            PlatformAgentEvent.PING_RESOURCE,
            PlatformAgentEvent.GET_RESOURCE,
            PlatformAgentEvent.SET_RESOURCE,

            PlatformAgentEvent.GET_SUBPLATFORM_IDS,

            PlatformAgentEvent.START_ALARM_DISPATCH,
            PlatformAgentEvent.STOP_ALARM_DISPATCH,
        ]


        def sort_caps(caps):
            agt_cmds = []
            agt_pars = []
            res_cmds = []
            res_pars = []

            if len(caps)>0 and isinstance(caps[0], AgentCapability):
                agt_cmds = [x.name for x in caps if x.cap_type==CapabilityType.AGT_CMD]
                agt_pars = [x.name for x in caps if x.cap_type==CapabilityType.AGT_PAR]
                res_cmds = [x.name for x in caps if x.cap_type==CapabilityType.RES_CMD]
                res_pars = [x.name for x in caps if x.cap_type==CapabilityType.RES_PAR]

            elif len(caps)>0 and isinstance(caps[0], dict):
                agt_cmds = [x['name'] for x in caps if x['cap_type']==CapabilityType.AGT_CMD]
                agt_pars = [x['name'] for x in caps if x['cap_type']==CapabilityType.AGT_PAR]
                res_cmds = [x['name'] for x in caps if x['cap_type']==CapabilityType.RES_CMD]
                res_pars = [x['name'] for x in caps if x['cap_type']==CapabilityType.RES_PAR]

            return agt_cmds, agt_pars, res_cmds, res_pars


        agt_pars_all = ['example']  # 'cause ResourceAgent defines aparam_example
        res_pars_all = []
        res_cmds_all = []

        ##################################################################
        # UNINITIALIZED
        ##################################################################

        self._assert_state(PlatformAgentState.UNINITIALIZED)

        # Get exposed capabilities in current state.
        retval = self._pa_client.get_capabilities()

        # Validate capabilities for state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_uninitialized = [
            PlatformAgentEvent.INITIALIZE,
            PlatformAgentEvent.GET_RESOURCE_CAPABILITIES,
        ]
        self.assertItemsEqual(agt_cmds, agt_cmds_uninitialized)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self._pa_client.get_capabilities(current_state=False)

        # Validate all capabilities as read from state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        self._initialize()

        ##################################################################
        # INACTIVE
        ##################################################################

        # Get exposed capabilities in current state.
        retval = self._pa_client.get_capabilities()

        # Validate capabilities for state INACTIVE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_inactive = [
            PlatformAgentEvent.RESET,
            PlatformAgentEvent.GET_SUBPLATFORM_IDS,
            PlatformAgentEvent.GO_ACTIVE,
            PlatformAgentEvent.PING_RESOURCE,
            PlatformAgentEvent.GET_RESOURCE_CAPABILITIES,
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_inactive)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self._pa_client.get_capabilities(False)

         # Validate all capabilities as read from state INACTIVE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        self._go_active()

        ##################################################################
        # IDLE
        ##################################################################

        # Get exposed capabilities in current state.
        retval = self._pa_client.get_capabilities()

         # Validate capabilities for state IDLE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_idle = [
            PlatformAgentEvent.RESET,
            PlatformAgentEvent.GO_INACTIVE,
            PlatformAgentEvent.RUN,
            PlatformAgentEvent.PING_RESOURCE,
            PlatformAgentEvent.GET_RESOURCE_CAPABILITIES,
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_idle)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states as read from IDLE.
        retval = self._pa_client.get_capabilities(False)

         # Validate all capabilities as read from state IDLE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        self._run()

        ##################################################################
        # COMMAND
        ##################################################################

        # Get exposed capabilities in current state.
        retval = self._pa_client.get_capabilities()

         # Validate capabilities of state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_command = [
            PlatformAgentEvent.GO_INACTIVE,
            PlatformAgentEvent.RESET,
            PlatformAgentEvent.GET_SUBPLATFORM_IDS,
            PlatformAgentEvent.GET_RESOURCE_CAPABILITIES,
            PlatformAgentEvent.PING_RESOURCE,
            PlatformAgentEvent.GET_RESOURCE,
            PlatformAgentEvent.SET_RESOURCE,

            PlatformAgentEvent.START_ALARM_DISPATCH,
            PlatformAgentEvent.STOP_ALARM_DISPATCH,
        ]

        res_cmds_command = [
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_command)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_command)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state COMMAND.
        retval = self._pa_client.get_capabilities(False)

         # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        self._go_inactive()
        self._reset()

    def test_go_active_and_run(self):

        log.info("test_go_active_and_run starting.  Default timeout=%s", TIMEOUT)

        self._ping_agent()

#        self._ping_resource() skipping this here while the timeout issue
#                              on r2_light and other builds is investigated.

        self._initialize()
        self._go_active()
        self._run()

        self._ping_agent()
        self._ping_resource()

        self._get_resource()
        self._set_resource()

        self._start_alarm_dispatch()

        self._wait_for_a_data_sample()

        self._stop_alarm_dispatch()

        self._get_subplatform_ids()

        self._go_inactive()
        self._reset()
