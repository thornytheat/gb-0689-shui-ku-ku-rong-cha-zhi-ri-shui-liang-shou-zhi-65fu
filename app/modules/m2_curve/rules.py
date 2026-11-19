import unicodedata
from app.normalize import number,instant
from app.errors import DomainError
from decimal import Decimal as D
from collections import defaultdict
from app.reasons import rejected
def validate_curve(points):
    if not isinstance(points,list) or len(points)<2:raise DomainError('CURVE','库容曲线至少两个点')
    try:curve=[(number(p[0]),number(p[1])) for p in points]
    except (TypeError,IndexError):raise DomainError('CURVE','曲线格式无效')
    if any(v<0 for _,v in curve) or any(b[0]<=a[0] or b[1]<=a[1] for a,b in zip(curve,curve[1:])):raise DomainError('CURVE','曲线必须严格递增')
    return curve
def optional(row,key):
    # 空单元格=该路未回传(可缺)；显式哨兵(NULL/未知等)=已报但无效,整行隔离。
    text=unicodedata.normalize('NFKC',str(row[key])).strip()
    if text=='':return None
    return number(text)
def normalize(row,curve):
    out=dict(row);out['time']=instant(row['time'])
    for key in ['level','inflow','outflow']:out[key]=optional(row,key)
    has_flow=out['inflow'] is not None or out['outflow'] is not None
    if has_flow and (out['inflow'] is None or out['outflow'] is None):raise DomainError('MISSING','入流或出流缺一')
    if out['level'] is None and not has_flow:raise DomainError('MISSING','测次既无水位也无流量')
    if has_flow:
        if row['flow_unit']=='L/s':out['inflow']/=1000;out['outflow']/=1000
        elif row['flow_unit']!='m3/s':raise DomainError('UNIT','流量单位无效')
        if out['inflow']<0 or out['outflow']<0:raise DomainError('RANGE','流量越界')
        out['flow_unit']='m3/s'
    if out['level'] is not None and not curve[0][0]<=out['level']<=curve[-1][0]:raise DomainError('RANGE','水位越界')
    v=number(row['version'])
    if v<1 or v!=v.to_integral():raise DomainError('RANGE','测次版本无效')
    out['version']=int(v);return out
def select(rows):
    groups=defaultdict(list)
    for row in rows:groups[(row['station'],row['time'])].append(row)
    good=[];bad=[]
    for key,group in sorted(groups.items()):
        latest=max(x['version'] for x in group);top=[x for x in group if x['version']==latest]
        merged={};conflict=False
        for field in ('level','inflow','outflow'):
            values={x[field] for x in top if x[field] is not None}
            if len(values)>1:conflict=True;break
            merged[field]=next(iter(values)) if values else None
        if conflict:bad.extend(rejected(x,'CONFLICT','同刻水文值矛盾') for x in group);continue
        base=min(top,key=lambda x:x['_line'])
        winner={**base,**merged}
        if winner['inflow'] is not None and base['inflow'] is None:
            winner['flow_unit']=next(x['flow_unit'] for x in top if x['inflow'] is not None)
        good.append(winner)
        bad.extend(rejected(x,'DUPLICATE','重复、旧版或已并入的测次') for x in group if x is not base)
    return good,bad
