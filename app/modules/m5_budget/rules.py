from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from collections import defaultdict
ZONE=timezone(timedelta(hours=8))
DAY_SECONDS=D(86400)
def pieces(part):
    # 把一段观测切成不跨+08:00日界的子段,子段首尾相接、互不重叠。
    start,end=part['start'],part['end'];cursor=start
    while cursor<end:
        local=cursor.astimezone(ZONE)
        midnight=datetime.combine(local.date()+timedelta(days=1),datetime.min.time(),ZONE)
        stop=min(end,midnight)
        yield local.date().isoformat(),cursor,stop
        cursor=stop
def at(part,key,t):
    # 相邻观测间线性变化;只在段内取值,不外推。
    start,end=part['start'],part['end'];duration=D(str((end-start).total_seconds()))
    return part['left'][key]+(part['right'][key]-part['left'][key])*D(str((t-start).total_seconds()))/duration
def merge(windows):
    # 首尾相接的覆盖窗口合并成不相交区间,作为交班依据时段。
    result=[]
    for s,e in sorted(windows):
        if result and result[-1][1]==s:result[-1][1]=e
        else:result.append([s,e])
    return result
def day_budget(flows,levels,curve,interpolate):
    # 流量体积与库容变化分轨入账:各自按本序列覆盖时段计算,收支差只取两轨共同覆盖的窗口。
    # 覆盖时长先累加整秒再一次性折算,避免分段除法的十进制尾数把满覆盖判成缺测。
    buckets=defaultdict(lambda:{'in_m3':D(0),'out_m3':D(0),'storage_change':D(0),'flow_seconds':D(0),'level_seconds':D(0),'compare_seconds':D(0),'flow_windows':[],'level_windows':[],'flow_pieces':[],'level_pieces':[],'compare_in':D(0),'compare_out':D(0),'compare_dv':D(0)})
    for part in flows:
        for day,s,e in pieces(part):
            b=buckets[(part['station'],day)];seconds=D(str((e-s).total_seconds()))
            b['in_m3']+=(at(part,'inflow',s)+at(part,'inflow',e))/2*seconds
            b['out_m3']+=(at(part,'outflow',s)+at(part,'outflow',e))/2*seconds
            b['flow_seconds']+=seconds;b['flow_windows'].append((s,e));b['flow_pieces'].append((part,s,e))
    for part in levels:
        for day,s,e in pieces(part):
            b=buckets[(part['station'],day)];seconds=D(str((e-s).total_seconds()))
            b['storage_change']+=interpolate(at(part,'level',e),curve)-interpolate(at(part,'level',s),curve)
            b['level_seconds']+=seconds;b['level_windows'].append((s,e));b['level_pieces'].append((part,s,e))
    result=[]
    for (station,day),b in sorted(buckets.items()):
        for fp,fs,fe in b['flow_pieces']:
            for lp,ls,le in b['level_pieces']:
                s,e=max(fs,ls),min(fe,le)
                if s<e:
                    seconds=D(str((e-s).total_seconds()))
                    b['compare_in']+=(at(fp,'inflow',s)+at(fp,'inflow',e))/2*seconds
                    b['compare_out']+=(at(fp,'outflow',s)+at(fp,'outflow',e))/2*seconds
                    b['compare_dv']+=interpolate(at(lp,'level',e),curve)-interpolate(at(lp,'level',s),curve)
                    b['compare_seconds']+=seconds
        if b['flow_seconds']==0 or b['level_seconds']==0:state='缺测'
        elif b['flow_seconds']==DAY_SECONDS and b['level_seconds']==DAY_SECONDS:state='完整'
        else:state='部分'
        residual=(b['compare_dv']-b['compare_in']+b['compare_out']) if b['compare_seconds']>0 else None
        result.append({'station':station,'date':day,'in_m3':b['in_m3'],'out_m3':b['out_m3'],'storage_change':b['storage_change'],
                       'flow_hours':b['flow_seconds']/3600,'level_hours':b['level_seconds']/3600,'compare_hours':b['compare_seconds']/3600,
                       'flow_windows':[[s.astimezone(ZONE).isoformat(),e.astimezone(ZONE).isoformat()] for s,e in merge(b['flow_windows'])],
                       'level_windows':[[s.astimezone(ZONE).isoformat(),e.astimezone(ZONE).isoformat()] for s,e in merge(b['level_windows'])],
                       'residual':residual,'state':state})
    return result
