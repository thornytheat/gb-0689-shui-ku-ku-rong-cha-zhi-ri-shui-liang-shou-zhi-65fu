from .rules import integrate
from app.normalize import number
def execute(ctx):
    flow_rows=[r for r in ctx['records'] if r['inflow'] is not None]
    parts,gaps=integrate(flow_rows,number(ctx['params']['max_gap_hours']));ctx['flows']=parts;ctx['gaps']=gaps
    ctx['stages'].append({'title':'流量积分','rows':parts,'metrics':{'流量测次':len(flow_rows),'有效段':len(parts),'缺口':len(gaps),'入库 m³':str(sum((x['in_m3'] for x in parts),0))}});return ctx
