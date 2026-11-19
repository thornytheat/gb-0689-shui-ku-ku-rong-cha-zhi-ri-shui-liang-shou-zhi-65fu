import pytest
from decimal import Decimal as D
from datetime import timedelta
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m5_budget.rules import day_budget
from app.modules.m4_storage.service import level_to_volume
from app.modules.m3_integrate.rules import integrate,chain
C=[(D(100),D(0)),(D(102),D(30000))]
def p(time,level):return dict(station='S',time=instant(time),inflow=D(1),outflow=D(0),level=D(level))
def budget(rows,gap=D(2)):
    flows,_=integrate(rows,gap);levels,_=chain(rows,gap)
    return day_budget(flows,levels,C,level_to_volume)

def test_midnight_split():
    # TRAP-23
    days=budget([p('2026-12-31T23:00:00+08:00','100'),p('2027-01-01T01:00:00+08:00','102')]);assert len(days)==2 and [r['in_m3'] for r in days]==[3600,3600]

def test_storage_conservation():
    assert sum(r['storage_change'] for r in budget([p('2026-11-16T23:00:00+08:00','100'),p('2026-11-17T01:00:00+08:00','102')]))==30000

def test_partial_day_handover_ready():
    # 覆盖不足的当天仍给出可交班结果,而不是整日判缺
    day=budget([p('2026-11-16T00:00:00Z','100'),p('2026-11-16T01:00:00Z','101')])[0]
    assert day['state']=='部分' and day['flow_hours']==1 and day['level_hours']==1 and day['compare_hours']==1

def test_missing_series_flagged():
    flows,_=integrate([dict(station='S',time=instant('2026-11-16T00:00:00Z'),inflow=D(1),outflow=D(0)),dict(station='S',time=instant('2026-11-16T01:00:00Z'),inflow=D(1),outflow=D(0))],D(2))
    day=day_budget(flows,[],C,level_to_volume)[0]
    assert day['state']=='缺测' and day['level_hours']==0 and day['residual'] is None

def test_empty():
    assert day_budget([],[],C,level_to_volume)==[]

def test_decoupled_windows():
    # 水位5分钟一路、流量1小时一路且错开:依据时段分别登记,互不拖累
    levels=[dict(station='S',time=instant('2026-11-16T00:00:00+08:00')+i*timedelta(minutes=5),level=D(100)+D('0.01')*i) for i in range(13)]
    flows=[dict(station='S',time=instant(f'2026-11-16T00:{m:02d}:00+08:00'),inflow=D(2),outflow=D(1)) for m in (20,50)]
    fparts,_=integrate(flows,D(2));lparts,_=chain(levels,D(2))
    day=day_budget(fparts,lparts,C,level_to_volume)[0]
    assert day['flow_windows']==[['2026-11-16T00:20:00+08:00','2026-11-16T00:50:00+08:00']]
    assert day['level_windows']==[['2026-11-16T00:00:00+08:00','2026-11-16T01:00:00+08:00']]
    assert day['flow_hours']==D('0.5') and day['level_hours']==1 and day['compare_hours']==D('0.5')
    # 收支差只按共同覆盖的00:20-00:50窗口计:库变0.06m×15000 - 入2×1800s + 出1×1800s
    assert day['residual']==D('0.06')*15000-D(2)*1800+D(1)*1800

def test_real_day_count(raw):
    assert len(run(raw,stop=5,persist=False)['budgets'])>=2

def test_real_partial_day(raw):
    assert any(x['state']=='部分' for x in run(raw,stop=5,persist=False)['budgets'])

def test_real_daily_integral(raw):
    x=run(raw,stop=5,persist=False);assert abs(sum(D(y['in_m3']) for y in x['budgets'])-sum(D(y['in_m3']) for y in x['flows']))<D('.000000001')

def test_real_windows_coverages_match(raw):
    # 依据时段与覆盖时长互相印证,交班依据可追溯
    from datetime import datetime
    for x in run(raw,stop=5,persist=False)['budgets']:
        for key,hours in (('flow_windows','flow_hours'),('level_windows','level_hours')):
            total=sum((datetime.fromisoformat(e)-datetime.fromisoformat(s)).total_seconds() for s,e in x[key])
            assert abs(D(str(total))-D(x[hours])*3600)<D('.000000001')
