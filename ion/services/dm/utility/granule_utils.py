#!/usr/bin/env python
'''
@author Luke Campbell <LCampbell@ASAScience.com>
@file ion/services/dm/utility/granule_utils.py
@date Wed Jul 18 09:00:22 EDT 2012
@description Utilities for crafting granules into a coverage
'''

from ion.services.dm.utility.granule import RecordDictionaryTool
from ion.util.time_utils import TimeUtils
from pyon.util.arg_check import validate_is_instance
from coverage_model.coverage import GridDomain, CRS, AxisTypeEnum, MutabilityEnum, GridShape, SimplexCoverage
from coverage_model.parameter import ParameterContext, ParameterDictionary 
from coverage_model.parameter_types import QuantityType
from pyon.public import log
import numpy as np
from numbers import Number
'''
Assuming all values are np.float64 except data which is int8
'''
class CoverageCraft(object):
    '''
    AKA the BlackBox
    PFM courtesy of Tommy Vandesteene
    '''
    def __init__(self,coverage=None, granule=None):
        if coverage is None:
            self.coverage = self.create_coverage()
            self.rdt = RecordDictionaryTool(param_dictionary=self.coverage.parameter_dictionary)
        else:
            self.coverage = coverage
            if granule is not None:
                self.sync_with_granule(granule)
            else:
                self.rdt = RecordDictionaryTool(param_dictionary=self.coverage.parameter_dictionary)
        self.pdict = self.coverage.parameter_dictionary


    def sync_rdt_with_granule(self, granule):
        rdt = RecordDictionaryTool.load_from_granule(granule)
        self.rdt = rdt
        return rdt

    def sync_with_granule(self, granule=None):
        if granule is not None:
            self.sync_rdt_with_granule(granule)
        if self.rdt is None:
            log.error('Failed to add granule, no granule assigned.')
            return
        start_index = self.coverage.num_timesteps 
        elements = self.rdt._shp[0]
        if not elements: return
        self.coverage.insert_timesteps(elements)

        for k,v in self.rdt.iteritems():
            log.info("key: %s" , k)
            log.info("value: %s" , v)
            slice_ = slice(start_index,None)
            log.info("slice: %s",  slice_)
            self.coverage.set_parameter_values(param_name=k,tdoa=slice_, value=v)


    def sync_rdt_with_coverage(self, coverage=None, tdoa=None, start_time=None, end_time=None, stride_time=None, parameters=None):
        '''
        Builds a granule based on the coverage
        '''
        if coverage is None:
            coverage = self.coverage

        slice_ = slice(None) # Defaults to all values
        if tdoa is not None and isinstance(tdoa,slice):
            slice_ = tdoa

        elif stride_time is not None:
            validate_is_instance(start_time, Number, 'start_time must be a number for striding.')
            validate_is_instance(end_time, Number, 'end_time must be a number for striding.')
            validate_is_instance(stride_time, Number, 'stride_time must be a number for striding.')
            ugly_range = np.arange(start_time, end_time, stride_time)
            idx_values = [TimeUtils.get_relative_time(coverage,i) for i in ugly_range]
            slice_ = [idx_values]

        elif not (start_time is None and end_time is None):
            time_var = coverage._temporal_param_name
            uom = coverage.get_parameter_context(time_var).uom
            if start_time is not None:
                start_units = TimeUtils.ts_to_units(uom,start_time)
                log.info('Units: %s', start_units)
                start_idx = TimeUtils.get_relative_time(coverage,start_units)
                log.info('Start Index: %s', start_idx)
                start_time = start_idx
            if end_time is not None:
                end_units   = TimeUtils.ts_to_units(uom,end_time)
                log.info('End units: %s', end_units)
                end_idx   = TimeUtils.get_relative_time(coverage,end_units)
                log.info('End index: %s',  end_idx)
                end_time = end_idx
            slice_ = slice(start_time,end_time,stride_time)
            log.info('Slice: %s', slice_)

        if parameters is not None:
            pdict = ParameterDictionary()
            params = set(coverage.list_parameters()).intersection(parameters)
            for param in params:
                pdict.add_context(coverage.get_parameter_context(param))
            rdt = RecordDictionaryTool(param_dictionary=pdict)
            self.pdict = pdict
        else:
            rdt = RecordDictionaryTool(param_dictionary=coverage.parameter_dictionary)
        
        fields = coverage.list_parameters()
        if parameters is not None:
            fields = set(fields).intersection(parameters)

        for d in fields:
            rdt[d] = coverage.get_parameter_values(d,tdoa=slice_)
        self.rdt = rdt # Sync

    def to_granule(self):
        return self.rdt.to_granule()

    @classmethod
    def create_coverage(cls):
        pdict = cls.create_parameters()
        sdom, tdom = cls.create_domains()
    
        scov = SimplexCoverage('sample grid coverage_model', pdict, tdom, sdom)

        return scov

    @classmethod
    def create_domains(cls):
        '''
        WARNING: This method is a wrapper intended only for tests, it should not be used in production code.
        It probably will not align to most datasets.
        '''
        tcrs = CRS([AxisTypeEnum.TIME])
        scrs = CRS([AxisTypeEnum.LON, AxisTypeEnum.LAT, AxisTypeEnum.HEIGHT])

        tdom = GridDomain(GridShape('temporal', [0]), tcrs, MutabilityEnum.EXTENSIBLE)
        sdom = GridDomain(GridShape('spatial', [0]), scrs, MutabilityEnum.IMMUTABLE) # Dimensionality is excluded for now
        return sdom, tdom

    @classmethod
    def create_parameters(cls):
        '''
        WARNING: This method is a wrapper intended only for tests, it should not be used in production code.
        It probably will not align to most datasets.
        '''
        pdict = ParameterDictionary()
        t_ctxt = ParameterContext('time', param_type=QuantityType(value_encoding=np.int64))
        t_ctxt.axis = AxisTypeEnum.TIME
        t_ctxt.uom = 'seconds since 1970-01-01'
        t_ctxt.fill_value = 0x0
        pdict.add_context(t_ctxt)

        lat_ctxt = ParameterContext('lat', param_type=QuantityType(value_encoding=np.float32))
        lat_ctxt.axis = AxisTypeEnum.LAT
        lat_ctxt.uom = 'degree_north'
        lat_ctxt.fill_value = 0e0
        pdict.add_context(lat_ctxt)

        lon_ctxt = ParameterContext('lon', param_type=QuantityType(value_encoding=np.float32))
        lon_ctxt.axis = AxisTypeEnum.LON
        lon_ctxt.uom = 'degree_east'
        lon_ctxt.fill_value = 0e0
        pdict.add_context(lon_ctxt)

        temp_ctxt = ParameterContext('temp', param_type=QuantityType(value_encoding=np.float32))
        temp_ctxt.uom = 'degree_Celsius'
        temp_ctxt.fill_value = 0e0
        pdict.add_context(temp_ctxt)

        cond_ctxt = ParameterContext('conductivity', param_type=QuantityType(value_encoding=np.float32))
        cond_ctxt.uom = 'unknown'
        cond_ctxt.fill_value = 0e0
        pdict.add_context(cond_ctxt)

        data_ctxt = ParameterContext('data', param_type=QuantityType(value_encoding=np.int8))
        data_ctxt.uom = 'byte'
        data_ctxt.fill_value = 0x0
        pdict.add_context(data_ctxt)

        pres_ctxt = ParameterContext('pressure', param_type=QuantityType(value_encoding=np.float32))
        pres_ctxt.uom = 'Pascal'
        pres_ctxt.fill_value = 0x0
        pdict.add_context(pres_ctxt)

        sal_ctxt = ParameterContext('salinity', param_type=QuantityType(value_encoding=np.float32))
        sal_ctxt.uom = 'PSU'
        sal_ctxt.fill_value = 0x0
        pdict.add_context(sal_ctxt)

        dens_ctxt = ParameterContext('density', param_type=QuantityType(value_encoding=np.float32))
        dens_ctxt.uom = 'unknown'
        dens_ctxt.fill_value = 0x0
        pdict.add_context(dens_ctxt)

        return pdict
        
    def build_coverage(self):
        pass

def time_series_domain():
    '''
    Domain set for simple time-series data
    '''
    tcrs = CRS([AxisTypeEnum.TIME])
    scrs = CRS([AxisTypeEnum.LON, AxisTypeEnum.LAT, AxisTypeEnum.HEIGHT])

    tdom = GridDomain(GridShape('temporal', [0]), tcrs, MutabilityEnum.EXTENSIBLE)
    sdom = GridDomain(GridShape('spatial', [0]), scrs, MutabilityEnum.IMMUTABLE) # Dimensionality is excluded for now
    return tdom, sdom

