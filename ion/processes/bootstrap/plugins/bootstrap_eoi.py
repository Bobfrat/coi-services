#!/usr/bin/env python

from ion.core.bootstrap_process import BootstrapPlugin
from pyon.public import Container
from interface.objects import IngestionQueue
from interface.services.dm.iingestion_management_service import IngestionManagementServiceProcessClient
from ion.services.eoi.table_loader import ResourceParser
from pyon.util.log import log

class BootstrapEOI(BootstrapPlugin):
    """
    Bootstrap process for EOI management.
    """

    def on_initial_bootstrap(self, process, config, **kwargs):
        """
        EOI BootstrapPlugin

        Resets the geoserver datastore... 
        """
        r = ResourceParser()
        try:
            r.init()
            r.reset()
        except Exception, e:
            log.error("Failed to reset and initialize eoi services", exc_info=True)
        
        
