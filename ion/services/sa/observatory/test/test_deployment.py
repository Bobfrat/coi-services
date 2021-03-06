#from interface.services.icontainer_agent import ContainerAgentClient
#from pyon.ion.endpoint import ProcessRPCClient
from interface.services.sa.idata_process_management_service import DataProcessManagementServiceClient

from ion.services.sa.test.helpers import any_old
from ion.util.enhanced_resource_registry_client import EnhancedResourceRegistryClient
from pyon.public import log, IonObject
from pyon.util.containers import DotDict
from pyon.util.int_test import IonIntegrationTestCase

from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.sa.iobservatory_management_service import ObservatoryManagementServiceClient
from interface.services.sa.iinstrument_management_service import InstrumentManagementServiceClient
from interface.services.sa.idata_product_management_service import DataProductManagementServiceClient
from interface.services.sa.idata_acquisition_management_service import DataAcquisitionManagementServiceClient
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from interface.services.dm.idataset_management_service import DatasetManagementServiceClient
from interface.objects import PortTypeEnum

from pyon.util.context import LocalContextMixin
from pyon.core.exception import NotFound, BadRequest
from pyon.public import RT, OT, PRED
#from mock import Mock, patch
from pyon.util.ion_time import IonTime
from nose.plugins.attrib import attr


import datetime

class FakeProcess(LocalContextMixin):
    name = ''


@attr('INT', group='sa')
class TestDeployment(IonIntegrationTestCase):

    def setUp(self):
        # Start container
        self._start_container()
        self.container.start_rel_from_url('res/deploy/r2deploy.yml')

        self.rrclient = ResourceRegistryServiceClient(node=self.container.node)
        self.omsclient = ObservatoryManagementServiceClient(node=self.container.node)
        self.imsclient = InstrumentManagementServiceClient(node=self.container.node)
        self.dmpsclient = DataProductManagementServiceClient(node=self.container.node)
        self.damsclient = DataAcquisitionManagementServiceClient(node=self.container.node)
        self.psmsclient = PubsubManagementServiceClient(node=self.container.node)
        self.dataset_management = DatasetManagementServiceClient()

        self.c = DotDict()
        self.c.resource_registry = self.rrclient
        self.RR2 = EnhancedResourceRegistryClient(self.rrclient)

        self.dsmsclient = DataProcessManagementServiceClient(node=self.container.node)


        # deactivate all data processes when tests are complete
        def killAllDataProcesses():
            for proc_id in self.rrclient.find_resources(RT.DataProcess, None, None, True)[0]:
                self.dsmsclient.deactivate_data_process(proc_id)
                self.dsmsclient.delete_data_process(proc_id)
        self.addCleanup(killAllDataProcesses)


    #@unittest.skip("targeting")
    def test_create_deployment(self):

        #create a deployment with metadata and an initial site and device
        platform_site__obj = IonObject(RT.PlatformSite,
                                        name='PlatformSite1',
                                        description='test platform site')
        site_id = self.omsclient.create_platform_site(platform_site__obj)

        platform_device__obj = IonObject(RT.PlatformDevice,
                                        name='PlatformDevice1',
                                        description='test platform device')
        device_id = self.imsclient.create_platform_device(platform_device__obj)

        start = IonTime(datetime.datetime(2013,1,1))
        end = IonTime(datetime.datetime(2014,1,1))
        temporal_bounds = IonObject(OT.TemporalBounds, name='planned', start_datetime=start.to_string(), end_datetime=end.to_string())
        deployment_obj = IonObject(RT.Deployment,
                                        name='TestDeployment',
                                        description='some new deployment',
                                        constraint_list=[temporal_bounds])
        deployment_id = self.omsclient.create_deployment(deployment_obj)
        self.omsclient.deploy_platform_site(site_id, deployment_id)
        self.imsclient.deploy_platform_device(device_id, deployment_id)

        log.debug("test_create_deployment: created deployment id: %s ", str(deployment_id) )

        #retrieve the deployment objects and check that the assoc site and device are attached
        read_deployment_obj = self.omsclient.read_deployment(deployment_id)
        log.debug("test_create_deployment: created deployment obj: %s ", str(read_deployment_obj) )

        site_ids, _ = self.rrclient.find_subjects(RT.PlatformSite, PRED.hasDeployment, deployment_id, True)
        self.assertEqual(len(site_ids), 1)

        device_ids, _ = self.rrclient.find_subjects(RT.PlatformDevice, PRED.hasDeployment, deployment_id, True)
        self.assertEqual(len(device_ids), 1)

        #delete the deployment
        self.RR2.pluck(deployment_id)
        self.omsclient.force_delete_deployment(deployment_id)
        # now try to get the deleted dp object
        try:
            self.omsclient.read_deployment(deployment_id)
        except NotFound:
            pass
        else:
            self.fail("deleted deployment was found during read")

    #@unittest.skip("targeting")
    def test_prepare_deployment_support(self):

        deploy_sup = self.omsclient.prepare_deployment_support()
        self.assertTrue(deploy_sup)
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].type_, "AssocDeploymentInstDevice")
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].associated_resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformDevice'].type_, "AssocDeploymentPlatDevice")
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformDevice'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformDevice'].associated_resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].type_, "AssocDeploymentInstSite")
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].associated_resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformSite'].type_, "AssocDeploymentPlatSite")
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformSite'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformSite'].associated_resources, [])

        #create a deployment with metadata and an initial site and device
        platform_site__obj = IonObject(RT.PlatformSite,
                                        name='PlatformSite1',
                                        description='test platform site')
        site_id = self.omsclient.create_platform_site(platform_site__obj)

        platform_device__obj = IonObject(RT.PlatformDevice,
                                        name='PlatformDevice1',
                                        description='test platform device')
        device_id = self.imsclient.create_platform_device(platform_device__obj)

        start = IonTime(datetime.datetime(2013,1,1))
        end = IonTime(datetime.datetime(2014,1,1))
        temporal_bounds = IonObject(OT.TemporalBounds, name='planned', start_datetime=start.to_string(), end_datetime=end.to_string())
        deployment_obj = IonObject(RT.Deployment,
                                        name='TestDeployment',
                                        description='some new deployment',
                                        constraint_list=[temporal_bounds])
        deployment_id = self.omsclient.create_deployment(deployment_obj)

        deploy_sup = self.omsclient.prepare_deployment_support(deployment_id)

        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].associated_resources, [])
        self.assertEquals(len(deploy_sup.associations['DeploymentHasPlatformDevice'].resources), 1)
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformDevice'].associated_resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].associated_resources, [])
        self.assertEquals(len(deploy_sup.associations['DeploymentHasPlatformSite'].resources), 1)
        self.assertEquals(deploy_sup.associations['DeploymentHasPlatformSite'].associated_resources, [])

        self.omsclient.assign_site_to_deployment(site_id, deployment_id)
        self.omsclient.assign_device_to_deployment(device_id, deployment_id)

        deploy_sup = self.omsclient.prepare_deployment_support(deployment_id)

        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentDevice'].associated_resources, [])
        self.assertEquals(len(deploy_sup.associations['DeploymentHasPlatformDevice'].resources), 1)
        self.assertEquals(len(deploy_sup.associations['DeploymentHasPlatformDevice'].associated_resources), 1)
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].resources, [])
        self.assertEquals(deploy_sup.associations['DeploymentHasInstrumentSite'].associated_resources, [])
        self.assertEquals(len(deploy_sup.associations['DeploymentHasPlatformSite'].resources), 1)
        self.assertEquals(len(deploy_sup.associations['DeploymentHasPlatformSite'].associated_resources), 1)

        #delete the deployment
        self.RR2.pluck(deployment_id)
        self.omsclient.force_delete_deployment(deployment_id)
        # now try to get the deleted dp object
        try:
            self.omsclient.read_deployment(deployment_id)
        except NotFound:
            pass
        else:
            self.fail("deleted deployment was found during read")


    #@unittest.skip("targeting")
    def base_activate_deployment(self):

        #-------------------------------------------------------------------------------------
        # Create platform site, platform device, platform model
        #-------------------------------------------------------------------------------------

        platform_site__obj = IonObject(RT.PlatformSite,
                                        name='PlatformSite1',
                                        description='test platform site')
        platform_site_id = self.omsclient.create_platform_site(platform_site__obj)

        platform_device_obj = IonObject(RT.PlatformDevice,
                                        name='PlatformDevice1',
                                        description='test platform device')
        platform_device_id = self.imsclient.create_platform_device(platform_device_obj)

        platform_model__obj = IonObject(RT.PlatformModel,
                                        name='PlatformModel1',
                                        description='test platform model')
        platform_model_id = self.imsclient.create_platform_model(platform_model__obj)



        #-------------------------------------------------------------------------------------
        # Create instrument site
        #-------------------------------------------------------------------------------------

        instrument_site_obj = IonObject(RT.InstrumentSite,
                                        name='InstrumentSite1',
                                        description='test instrument site')
        instrument_site_id = self.omsclient.create_instrument_site(instrument_site_obj, platform_site_id)

        pdict_id = self.dataset_management.read_parameter_dictionary_by_name('ctd_parsed_param_dict', id_only=True)
        ctd_stream_def_id = self.psmsclient.create_stream_definition(name='SBE37_CDM', parameter_dictionary_id=pdict_id)


        #----------------------------------------------------------------------------------------------------
        # Create an instrument device
        #----------------------------------------------------------------------------------------------------

        instrument_device_obj = IonObject(RT.InstrumentDevice,
                                        name='InstrumentDevice1',
                                        description='test instrument device')
        instrument_device_id = self.imsclient.create_instrument_device(instrument_device_obj)
        self.rrclient.create_association(platform_device_id, PRED.hasDevice, instrument_device_id)



        #----------------------------------------------------------------------------------------------------
        # Create an instrument model
        #----------------------------------------------------------------------------------------------------

        instrument_model_obj = IonObject(RT.InstrumentModel,
                                        name='InstrumentModel1',
                                        description='test instrument model')
        instrument_model_id = self.imsclient.create_instrument_model(instrument_model_obj)


        #----------------------------------------------------------------------------------------------------
        # Create a deployment object
        #----------------------------------------------------------------------------------------------------

        start = IonTime(datetime.datetime(2013,1,1))
        end = IonTime(datetime.datetime(2014,1,1))
        temporal_bounds = IonObject(OT.TemporalBounds, name='planned', start_datetime=start.to_string(), end_datetime=end.to_string())
        deployment_obj = IonObject(RT.Deployment,
                                   name='TestDeployment',
                                   description='some new deployment',
                                   context=IonObject(OT.CabledNodeDeploymentContext),
                                   constraint_list=[temporal_bounds])
        deployment_id = self.omsclient.create_deployment(deployment_obj)

        log.debug("test_create_deployment: created deployment id: %s ", str(deployment_id) )


        ret = DotDict(instrument_site_id=instrument_site_id,
                      instrument_device_id=instrument_device_id,
                      instrument_model_id=instrument_model_id,
                      platform_site_id=platform_site_id,
                      platform_device_id=platform_device_id,
                      platform_model_id=platform_model_id,
                      deployment_id=deployment_id)


        return ret

    #@unittest.skip("targeting")
    def test_activate_deployment_normal(self):

        res = self.base_activate_deployment()

        log.debug("assigning platform and instrument models")
        self.imsclient.assign_platform_model_to_platform_device(res.platform_model_id, res.platform_device_id)
        self.imsclient.assign_instrument_model_to_instrument_device(res.instrument_model_id, res.instrument_device_id)
        self.omsclient.assign_platform_model_to_platform_site(res.platform_model_id, res.platform_site_id)
        self.omsclient.assign_instrument_model_to_instrument_site(res.instrument_model_id, res.instrument_site_id)

        log.debug("adding instrument site and device to deployment")
        self.omsclient.deploy_instrument_site(res.instrument_site_id, res.deployment_id)
        self.imsclient.deploy_instrument_device(res.instrument_device_id, res.deployment_id)

        log.debug("adding platform site and device to deployment")
        self.omsclient.deploy_platform_site(res.platform_site_id, res.deployment_id)
        self.imsclient.deploy_platform_device(res.platform_device_id, res.deployment_id)

        log.debug("activating deployment, expecting success")
        self.omsclient.activate_deployment(res.deployment_id)

        log.debug("deactivatin deployment, expecting success")
        self.omsclient.deactivate_deployment(res.deployment_id)

    #@unittest.skip("targeting")
    def test_activate_deployment_nomodels(self):

        res = self.base_activate_deployment()

        self.omsclient.deploy_instrument_site(res.instrument_site_id, res.deployment_id)
        self.imsclient.deploy_instrument_device(res.instrument_device_id, res.deployment_id)

        log.debug("activating deployment without site+device models, expecting fail")
        self.assert_deploy_fail(res.deployment_id, NotFound, "Expected 1")

        log.debug("assigning instrument site model")
        self.omsclient.assign_instrument_model_to_instrument_site(res.instrument_model_id, res.instrument_site_id)

        log.debug("activating deployment without device models, expecting fail")
        self.assert_deploy_fail(res.deployment_id, NotFound, "Expected 1")

    #@unittest.skip("targeting")
    def test_activate_deployment_nosite(self):

        res = self.base_activate_deployment()

        log.debug("assigning instrument models")
        self.imsclient.assign_instrument_model_to_instrument_device(res.instrument_model_id, res.instrument_device_id)
        self.omsclient.assign_instrument_model_to_instrument_site(res.instrument_model_id, res.instrument_site_id)

        log.debug("deploying instrument device only")
        self.imsclient.deploy_instrument_device(res.instrument_device_id, res.deployment_id)

        log.debug("activating deployment without instrument site, expecting fail")
        self.assert_deploy_fail(res.deployment_id, BadRequest, "Devices in this deployment outnumber sites")

    #@unittest.skip("targeting")
    def test_activate_deployment_nodevice(self):

        res = self.base_activate_deployment()

        log.debug("assigning platform and instrument models")
        self.imsclient.assign_instrument_model_to_instrument_device(res.instrument_model_id, res.instrument_device_id)
        self.omsclient.assign_instrument_model_to_instrument_site(res.instrument_model_id, res.instrument_site_id)

        log.debug("deploying instrument site only")
        self.omsclient.deploy_instrument_site(res.instrument_site_id, res.deployment_id)

        log.debug("activating deployment without device, expecting fail")
        self.assert_deploy_fail(res.deployment_id, BadRequest, "No devices were found in the deployment")


    def test_activate_deployment_asymmetric_children(self):
        """
        P0
        |  \
        P1  P2
        |
        I1

        Complex deployment using CSP

        P1, P2, and P3 share the same platform model.  The CSP solver should be able to work this out
        based on relationships to parents

        """

        log.debug("create models")
        imodel_id = self.RR2.create(any_old(RT.InstrumentModel))
        pmodel_id = self.RR2.create(any_old(RT.PlatformModel))

        log.debug("create devices")
        idevice_id = self.RR2.create(any_old(RT.InstrumentDevice))
        pdevice_id = [self.RR2.create(any_old(RT.PlatformDevice)) for _ in range(3)]

        log.debug("create sites")
        isite_id = self.RR2.create(any_old(RT.InstrumentSite))
        psite_id = [self.RR2.create(any_old(RT.PlatformSite)) for _ in range(3)]

        log.debug("assign models")
        self.RR2.assign_instrument_model_to_instrument_device_with_has_model(imodel_id, idevice_id)
        self.RR2.assign_instrument_model_to_instrument_site_with_has_model(imodel_id, isite_id)
        for x in range(3):
            self.RR2.assign_platform_model_to_platform_device_with_has_model(pmodel_id, pdevice_id[x])
            self.RR2.assign_platform_model_to_platform_site_with_has_model(pmodel_id, psite_id[x])

        log.debug("assign hierarchy")
        self.RR2.assign_instrument_device_to_platform_device_with_has_device(idevice_id, pdevice_id[1])
        self.RR2.assign_instrument_site_to_platform_site_with_has_site(isite_id, psite_id[1])
        for x in range(1,3):
            self.RR2.assign_platform_device_to_platform_device_with_has_device(pdevice_id[x], pdevice_id[0])
            self.RR2.assign_platform_site_to_platform_site_with_has_site(psite_id[x], psite_id[0])

        log.debug("create and activate deployment")
        dep_id = self.RR2.create(any_old(RT.Deployment, {"context": IonObject(OT.RemotePlatformDeploymentContext)}))
        self.RR2.assign_deployment_to_platform_device_with_has_deployment(dep_id, pdevice_id[0])
        self.RR2.assign_deployment_to_platform_site_with_has_deployment(dep_id, psite_id[0])
        self.omsclient.activate_deployment(dep_id)

        log.debug("verifying deployment")
        self.assertEqual(idevice_id, self.RR2.find_instrument_device_id_of_instrument_site_using_has_device(isite_id),
                         "The instrument device was not assigned to the instrument site")
        for x in range(3):
            self.assertEqual(pdevice_id[x], self.RR2.find_platform_device_id_of_platform_site_using_has_device(psite_id[x]),
                             "Platform device %d was not assigned to platform site %d" % (x, x))

    def assert_deploy_fail(self, deployment_id, err_type=BadRequest, fail_message="did not specify fail_message"):
        with self.assertRaises(err_type) as cm:
            self.omsclient.activate_deployment(deployment_id)
        self.assertIn(fail_message, cm.exception.message)

    def test_3x3_matchups_remoteplatform(self):
        self.base_3x3_matchups(IonObject(OT.RemotePlatformDeploymentContext))

    def test_3x3_matchups_cabledinstrument(self):
        self.base_3x3_matchups(IonObject(OT.CabledInstrumentDeploymentContext))

    def test_3x3_matchups_cablednode(self):
        self.base_3x3_matchups(IonObject(OT.CabledNodeDeploymentContext))

    def base_3x3_matchups(self, deployment_context):
        """
        This will be 1 root platform, 3 sub platforms (2 of one model, 1 of another) and 3 sub instruments each (2-to-1)
        """
        deployment_context_type = type(deployment_context).__name__

        instrument_model_id  = [self.RR2.create(any_old(RT.InstrumentModel)) for _ in range(6)]
        platform_model_id    = [self.RR2.create(any_old(RT.PlatformModel)) for _ in range(3)]

        instrument_device_id = [self.RR2.create(any_old(RT.InstrumentDevice)) for _ in range(9)]
        platform_device_id   = [self.RR2.create(any_old(RT.PlatformDevice)) for _ in range(4)]

        instrument_site_id   = [self.RR2.create(any_old(RT.InstrumentSite,
                                                { "reference_designator" : "GA01SUMO-FI003-0%s-CTDMO0999" % (i+1),
                                                    "planned_uplink_port":
                                                     IonObject(OT.PlatformPort,
                                                               reference_designator="GA01SUMO-FI003-0%s-CTDMO0999" % (i+1) )}))
                                for i in range(9)]

        platform_site_id     = [self.RR2.create(any_old(RT.PlatformSite,
                                                {  "reference_designator" : "GA01SUMO-FI003-0%s-CTDMO0888" % (i+1) ,
                                                    "planned_uplink_port":
                                                    IonObject(OT.PlatformPort,
                                                              reference_designator="GA01SUMO-FI003-0%s-CTDMO0888" % (i+1))}))
                                for i in range(4)]



        def instrument_model_at(platform_idx, instrument_idx):
            m = platform_idx * 2
            if instrument_idx > 0:
                m += 1
            return m

        def platform_model_at(platform_idx):
            if platform_idx > 0:
                return 1
            return 0

        def instrument_at(platform_idx, instrument_idx):
            return platform_idx * 3 + instrument_idx

        # set up the structure
        for p in range(3):
            m = platform_model_at(p)
            self.RR2.assign_platform_model_to_platform_site_with_has_model(platform_model_id[m], platform_site_id[p])
            self.RR2.assign_platform_model_to_platform_device_with_has_model(platform_model_id[m], platform_device_id[p])
            self.RR2.assign_platform_device_to_platform_device_with_has_device(platform_device_id[p], platform_device_id[3])
            self.RR2.assign_platform_site_to_platform_site_with_has_site(platform_site_id[p], platform_site_id[3])

            for i in range(3):
                m = instrument_model_at(p, i)
                idx = instrument_at(p, i)
                self.RR2.assign_instrument_model_to_instrument_site_with_has_model(instrument_model_id[m], instrument_site_id[idx])
                self.RR2.assign_instrument_model_to_instrument_device_with_has_model(instrument_model_id[m], instrument_device_id[idx])
                self.RR2.assign_instrument_device_to_platform_device_with_has_device(instrument_device_id[idx], platform_device_id[p])
                self.RR2.assign_instrument_site_to_platform_site_with_has_site(instrument_site_id[idx], platform_site_id[p])

        # top level models
        self.RR2.assign_platform_model_to_platform_device_with_has_model(platform_model_id[2], platform_device_id[3])
        self.RR2.assign_platform_model_to_platform_site_with_has_model(platform_model_id[2], platform_site_id[3])



        # verify structure
        for p in range(3):
            parent_id = self.RR2.find_platform_device_id_by_platform_device_using_has_device(platform_device_id[p])
            self.assertEqual(platform_device_id[3], parent_id)

            parent_id = self.RR2.find_platform_site_id_by_platform_site_using_has_site(platform_site_id[p])
            self.assertEqual(platform_site_id[3], parent_id)

        for i in range(len(platform_site_id)):
            self.assertEqual(self.RR2.find_platform_model_of_platform_device_using_has_model(platform_device_id[i]),
                             self.RR2.find_platform_model_of_platform_site_using_has_model(platform_site_id[i]))

        for i in range(len(instrument_site_id)):
            self.assertEqual(self.RR2.find_instrument_model_of_instrument_device_using_has_model(instrument_device_id[i]),
                             self.RR2.find_instrument_model_of_instrument_site_using_has_model(instrument_site_id[i]))


        # OOIReferenceDesignator format: GA01SUMO-FI003-03-CTDMO0999  (site-platform_id-port-device_id)

        port_assignments = {}
        for p in range(3):
            ref_desig = "GA01SUMO-FI003-0%s-CTDMO0888" % (p+1)
            pp_obj = IonObject(OT.PlatformPort, reference_designator=ref_desig, port_type= PortTypeEnum.PAYLOAD, ip_address=str(p) )
            port_assignments[platform_device_id[p]] = pp_obj
            for i in range(3):
                ref_desig = "GA01SUMO-FI003-0%s-CTDMO0999" % ((p*3)+i+1)
                pp_obj = IonObject(OT.PlatformPort, reference_designator=ref_desig, port_type= PortTypeEnum.PAYLOAD, ip_address=str(p) )
                idx = instrument_at(p, i)
                port_assignments[instrument_device_id[idx]] = pp_obj

        deployment_id = self.RR2.create(any_old(RT.Deployment,
                {"context": deployment_context,
                 "port_assignments": port_assignments}))


        log.debug("assigning device/site to %s deployment", deployment_context_type)
        if OT.RemotePlatformDeploymentContext == deployment_context_type:
            self.RR2.assign_deployment_to_platform_device_with_has_deployment(deployment_id, platform_device_id[3])
            self.RR2.assign_deployment_to_platform_site_with_has_deployment(deployment_id, platform_site_id[3])

        elif OT.CabledInstrumentDeploymentContext == deployment_context_type:
            self.RR2.assign_deployment_to_instrument_device_with_has_deployment(deployment_id, instrument_device_id[1])
            self.RR2.assign_deployment_to_instrument_site_with_has_deployment(deployment_id, instrument_site_id[1])

        elif OT.CabledNodeDeploymentContext == deployment_context_type:
            self.RR2.assign_deployment_to_platform_device_with_has_deployment(deployment_id, platform_device_id[1])
            self.RR2.assign_deployment_to_platform_site_with_has_deployment(deployment_id, platform_site_id[1])

        log.debug("activation of %s deployment", deployment_context_type)
        self.omsclient.activate_deployment(deployment_id)

        log.debug("validation of %s deployment", deployment_context_type)
        if OT.RemotePlatformDeploymentContext == deployment_context_type:
            # verify proper associations
            for i, d in enumerate(platform_device_id):
                self.assertEqual(d, self.RR2.find_platform_device_id_of_platform_site_using_has_device(platform_site_id[i]))

            for i, d in enumerate(instrument_device_id):
                self.assertEqual(d, self.RR2.find_instrument_device_id_of_instrument_site_using_has_device(instrument_site_id[i]))

        elif OT.CabledInstrumentDeploymentContext == deployment_context_type:
            self.assertEqual(instrument_device_id[1],
                             self.RR2.find_instrument_device_id_of_instrument_site_using_has_device(instrument_site_id[1]))

        elif OT.CabledNodeDeploymentContext == deployment_context_type:
            expected_platforms = [1]

            # verify proper associations
            for i, d in enumerate(platform_device_id):
                self.assertEqual(i in expected_platforms,
                                 d in self.RR2.find_platform_device_ids_of_platform_site_using_has_device(platform_site_id[i]))


        # site and device are no longer collected using four lists (expecting two to be empty, the other two to match)
        # so these assertions no longer have the same meaning
        #extended_deployment = self.omsclient.get_deployment_extension(deployment_id)
        #log.debug('base_3x3_matchups extended_deployment:  %s', extended_deployment)
        #self.assertTrue(len(extended_deployment.platform_sites) == len(extended_deployment.platform_devices),
        #    msg='%d sites but %d devices' % (len(extended_deployment.platform_sites), len(extended_deployment.platform_devices)))
        #self.assertTrue(len(extended_deployment.instrument_sites) == len(extended_deployment.instrument_devices),
        #    msg='%d sites but %d devices' % (len(extended_deployment.instrument_sites), len(extended_deployment.instrument_devices)))
        #self.assertTrue(len(extended_deployment.instrument_devices) == len(extended_deployment.instrument_models))
        #self.assertTrue(len(extended_deployment.platform_devices) == len(extended_deployment.platform_models))



