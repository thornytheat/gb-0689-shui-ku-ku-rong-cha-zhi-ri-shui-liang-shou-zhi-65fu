from collections import defaultdict
from decimal import Decimal as D
def chain(rows,max_gap):
    # 把一条独立序列(流量或水位)按事件时刻排序并连成相邻段;超过max_gap不插补,登记缺口。
    stations=defaultdict(list)
    for row in rows:stations[row['station']].append(row)
    parts=[];gaps=[]
    for station,items in sorted(stations.items()):
        items=sorted(items,key=lambda r:r['time'])
        for a,b in zip(items,items[1:]):
            seconds=D(str((b['time']-a['time']).total_seconds()))
            if seconds>max_gap*3600:
                gaps.append({'station':station,'start':a['time'],'end':b['time'],'hours':seconds/3600,'code':'GAP','state':'缺测'});continue
            parts.append({'station':station,'start':a['time'],'end':b['time'],'left':a,'right':b})
    return parts,gaps
def integrate(rows,max_gap):
    parts,gaps=chain(rows,max_gap)
    for part in parts:
        seconds=D(str((part['end']-part['start']).total_seconds()))
        part['in_m3']=(part['left']['inflow']+part['right']['inflow'])/2*seconds
        part['out_m3']=(part['left']['outflow']+part['right']['outflow'])/2*seconds
    return parts,gaps
