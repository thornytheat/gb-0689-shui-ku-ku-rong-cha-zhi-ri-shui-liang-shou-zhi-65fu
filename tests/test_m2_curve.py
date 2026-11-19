import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m2_curve.rules import validate_curve,normalize,select
CURVE=validate_curve([['100','0'],['102','30000'],['105','100000']])
def row(**kw):
 x=dict(id='1',station='甲库',time='2026-11-16T00:00:00Z',level='101',inflow='1',outflow='0',flow_unit='m3/s',version='1',_line=2);x.update(kw);return x

def test_fullwidth():
    # TRAP-06
    assert normalize(row(level='１０１'),CURVE)['level']==101

def test_unit_conversion():
    # TRAP-15
    assert normalize(row(inflow='1,000',flow_unit='L/s'),CURVE)['inflow']==1

def test_sentinel():
    # TRAP-07
    with pytest.raises(DomainError):normalize(row(level='未知'),CURVE)

def test_level_only_row_accepted():
    # 水位电报(流量未回传)可采信,流量字段留空
    x=normalize(row(inflow='',outflow='',flow_unit=''),CURVE)
    assert x['level']==101 and x['inflow'] is None and x['outflow'] is None

def test_flow_only_row_accepted():
    # 流量电报(无水位)可采信,单位照常归一
    x=normalize(row(level='',inflow='2,200',outflow='1,500',flow_unit='L/s'),CURVE)
    assert x['level'] is None and x['inflow']==D('2.2') and x['outflow']==D('1.5') and x['flow_unit']=='m3/s'

def test_half_flow_rejected():
    # 入流出流缺一不成流量,整行隔离
    with pytest.raises(DomainError):normalize(row(outflow=''),CURVE)

def test_neither_field_rejected():
    with pytest.raises(DomainError):normalize(row(level='',inflow='',outflow='',flow_unit=''),CURVE)

def test_complementary_streams_merged():
    # 同刻水位报与流量报互补合并,不丢任何一路
    a=normalize(row(id='L1',inflow='',outflow='',flow_unit='',_line=2),CURVE)
    b=normalize(row(id='F1',level='',_line=3),CURVE)
    good,bad=select([a,b])
    assert len(good)==1 and good[0]['level']==101 and good[0]['inflow']==1 and len(bad)==1 and bad[0]['code']=='DUPLICATE'

def test_same_value_conflict_still_isolated():
    # TRAP-14:同刻同版水位矛盾仍整组隔离
    a=normalize(row(id='1',level='102',_line=2),CURVE)
    b=normalize(row(id='2',level='103',_line=3),CURVE)
    good,bad=select([a,b])
    assert good==[] and len(bad)==2 and all(x['code']=='CONFLICT' for x in bad)

def test_curve_monotonic():
    with pytest.raises(DomainError):validate_curve([[100,10],[101,9]])

def test_real_conflict(raw):
    # TRAP-14
    assert sum(x['code']=='CONFLICT' for x in run(raw,stop=2,persist=False)['quarantine'])==2

def test_real_curve(raw):
    assert len(run(raw,stop=2,persist=False)['curve'])==4

def test_real_valid_units(raw):
    assert all(x['flow_unit']=='m3/s' for x in run(raw,stop=2,persist=False)['records'])

