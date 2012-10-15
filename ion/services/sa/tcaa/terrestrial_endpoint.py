#!/usr/bin/env python
"""
@package ion.services.sa.tcaa.terrestrial_endpoint
@file ion/services/sa/tcaa/terrestrial_endpoint.py
@author Edward Hunter
@brief 2CAA Terrestrial endpoint.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

# Pyon log and config objects.
from pyon.public import log
from pyon.public import CFG

import uuid
import time

# Pyon exceptions.
from pyon.core.exception import BadRequest
from pyon.core.exception import Conflict
from pyon.core.exception import ConfigNotFound

from pyon.event.event import EventPublisher, EventSubscriber
from interface.objects import TelemetryStatusType, RemoteCommand

from interface.services.sa.iterrestrial_endpoint import BaseTerrestrialEndpoint
from interface.services.sa.iterrestrial_endpoint import TerrestrialEndpointProcessClient
from ion.services.sa.tcaa.endpoint_mixin import EndpointMixin

class TerrestrialEndpoint(BaseTerrestrialEndpoint, EndpointMixin):
    """
    Terrestrial endpoint for two component agent architecture.
    This class provides a manipulable terrestrial command queue and fully
    asynchronous command and result transmission between shore and remote
    containers.
    """
    def __init__(self, *args, **kwargs):
        """
        For framework level code only.
        """
        super(TerrestrialEndpoint, self).__init__(*args, **kwargs)

    ######################################################################    
    # Framework process lifecycle functions.
    ######################################################################    
    
    def on_init(self):
        """
        Application level initializer.
        Setup default internal values.
        """
        super(BaseTerrestrialEndpoint, self).on_init()
        self.mixin_on_init()
        self._tx_dict = {}
        if not self.CFG.xs_name:
            raise ConfigNotFound('Terrestrial endpoint missing required xs_name parameter.')
        self._xs_name = self.CFG.xs_name    
    
    def on_start(self):
        """
        Process about to be started.
        Create client and server R3PC sockets.
        Start server.
        Start telemetry subscriber.
        """
        super(BaseTerrestrialEndpoint, self).on_start()
        self.mixin_on_start()
                        
    def on_stop(self):
        """
        Process about to be stopped.
        Stop sockets and subscriber.
        """
        self.mixin_on_stop()
        super(BaseTerrestrialEndpoint, self).on_stop()
    
    def on_quit(self):
        """
        Process terminated following.
        Stop sockets and subscriber.
        """
        self.mixin_on_quit()
        super(BaseTerrestrialEndpoint, self).on_quit()

    ######################################################################    
    # Callbacks.
    ######################################################################    

    def _req_callback(self, result):
        """
        Terrestrial server callback for result receipts.
        Pop pending command, append result and publish.
        """
        log.debug('Terrestrial server got result: %s', str(result))
        
        try:
            id = result['command_id']
            _result = result['result']
            cmd = self._tx_dict.pop(id)
            cmd.time_completed = time.time()
            cmd.result = _result
            if cmd.resource_id:
                origin = cmd.resource_id
            elif cmd.svc_name:
                origin = cmd.svc_name + self._xs_name
            else:
                raise KeyError
            
            self._publisher.publish_event(
                                    event_type='RemoteCommandResult',
                                    command=cmd,
                                    origin=origin)
            log.debug('Published remote result: %s.', str(result))
        except KeyError:
            log.warning('#############################################')
            log.warning('Error publishing remote result: %s.', str(_result))
            log.warning('Command: %s.', str(cmd))
            log.warning('Result: %s.', str(_result))
            
    def _ack_callback(self, request):
        """
        Terrestrial client callback for command transmission acks.
        Insert command into pending command dictionary.
        """
        log.debug('Terrestrial client got ack for request: %s', str(request))
        #self._tx_dict[request.command_id] = request
        self._publisher.publish_event(
                                event_type='RemoteCommandTransmittedEvent',
                                origin=self._xs_name,
                                queue_size=len(self._client._queue))        

    def _server_close_callback(self):
        """
        Terrestrial server has closed.
        """
        log.debug('Terrestrial endpoint server closed.')    
    
    def _client_close_callback(self):
        """
        Terrestrial client has closed.
        """
        log.debug('Terrestrial endpoint client closed.')

    def _consume_telemetry_event(self, *args, **kwargs):
        """
        Telemetry event callback.
        Trigger link up or link down processing as needed.
        """
        log.debug('Telemetry event received by terrestrial endpoint, args: %s, kwargs: %s',
                  str(args), str(kwargs))
        evt = args[0]
        self._link_status = evt.status
        if evt.status == TelemetryStatusType.AVAILABLE:
            log.debug('Telemetry available.')
            self._on_link_up()
            
        elif evt.status == TelemetryStatusType.UNAVAILABLE:
            log.debug('Telemetry not available.')
            self._on_link_down()

    def _on_link_up(self):
        """
        Processing on link up event.
        Start client socket.
        ION link availability published when pending commands are transmitted.
        """
        log.debug('%s client connecting to %s:%i',
                    self.__class__.__name__,
                    self._other_host, self._other_port)
        self._client.start(self._other_host, self._other_port)
        self._publisher.publish_event(
                                event_type='PublicPlatformTelemetryEvent',
                                origin=self._xs_name,
                                status=TelemetryStatusType.AVAILABLE)        

    def _on_link_down(self):
        """
        Processing on link down event.
        Stop client socket and publish ION link unavailability.
        """
        self._client.stop()
        self._publisher.publish_event(
                                event_type='PublicPlatformTelemetryEvent',
                                origin=self._xs_name,
                                status=TelemetryStatusType.UNAVAILABLE)        
        
    ######################################################################    
    # Commands.
    ######################################################################    

    def enqueue_command(self, command=None, link=False):
        """
        Enqueue command for remote processing.
        """
        if link and self._link_status != TelemetryStatusType.AVAILABLE:
            return
        
        if not isinstance(command, RemoteCommand):
            return
        
        command.time_queued = time.time()
        command.command_id = str(uuid.uuid4())
        self._tx_dict[command.command_id] = command
        self._client.enqueue(command)
        self._publisher.publish_event(
                                event_type='RemoteQueueModifiedEvent',
                                origin=self._xs_name,
                                queue_size=len(self._client._queue))        
        return command
    
    def get_queue(self, resource_id=''):
        """
        Retrieve the command queue by resource id.
        """
        if resource_id == '':
            result = list(self._client._queue)
        else:
            result = [x for x in self._client._queue if x.resource_id == resource_id]

        return result

    def clear_queue(self, resource_id=''):
        """
        Clear the command queue by resource id.
        Only availabile in offline mode.
        """
        popped = []
        if self._link_status == TelemetryStatusType.UNAVAILABLE:
            if resource_id == '':
                new_queue = []
                popped = self._client._queue
            else:
                new_queue = [x for x in self._client._queue if x.resource_id != resource_id]
                popped = [x for x in self._client._queue if x.resource_id == resource_id]
            
            for x in popped:
                if x.command_id in self._tx_dict:
                    self._tx_dict.pop(x.command_id)
                    
            self._client._queue = new_queue
            if len(popped)>0:
                self._publisher.publish_event(
                                event_type='RemoteQueueModifiedEvent',
                                origin=self._xs_name,
                                queue_size=len(self._client._queue))        
            
        return popped

    def pop_queue(self, command_id=''):
        """
        Pop command queue by command id.
        Only available in offline mode.
        """
        poped = None
        if self._link_status == TelemetryStatusType.UNAVAILABLE:
            for x in range(len(self._client._queue)):
                if self._client._queue[x].command_id == command_id:
                    poped = self._client._queue.pop(x)
                    if poped.command_id in self._tx_dict:
                        self._tx_dict.pop(poped.command_id)
                        
                    self._publisher.publish_event(
                                event_type='RemoteQueueModifiedEvent',
                                origin=self._xs_name,
                                queue_size=len(self._client._queue))
                    break
                    
        return poped
    
    def get_pending(self, resource_id=''):
        """
        Retrieve pending commands by resource id.
        """
        if resource_id == '':
            pending = self._tx_dict.values()
        
        else:
            pending = []
            for (key,val) in self._tx_dict.iteritems():
                if val.resource_id == resource_id:
                    pending.append(val)
        return pending

    def clear_pending(self, resource_id=''):
        """
        Clear pending commands by resource id.
        """
        if resource_id == '':
            pending = self._tx_dict.values()
            self._tx_dict = {}
            
        else:
            pending = []
            for (key,val) in self._tx_dict.iteritems():
                if val.resource_id == resource_id:
                    pending.append(val)
                    self._tx_dict.pop(key)
        return pending

    def get_port(self):
        """
        Retrieve the terrestrial server port.
        """
        return self._this_port

    def set_client_port(self, port):
        """
        Set the terrestrial client port.
        """
        self._other_port = port

    def get_client_port(self):
        """
        Get the terrestrial client port.
        """
        return self._other_port


class TerrestrialEndpointClient(TerrestrialEndpointProcessClient):
    """
    Terrestrial endpoint client.
    """
    pass
