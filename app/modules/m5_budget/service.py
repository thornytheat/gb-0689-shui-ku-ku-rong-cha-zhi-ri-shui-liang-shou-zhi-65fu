from .rules import day_budget
from app.modules.m4_storage.service import level_to_volume
from app.modules.m3_integrate.rules import chain
from app.normalize import number
def execute(ctx):
    level_rows=[r for r in ctx['records'] if r['level'] is not None]
    parts,gaps=chain(level_rows,number(ctx['params']['max_gap_hours']))
    ctx['level_parts']=parts;ctx['level_gaps']=gaps
    rows=day_budget(ctx['flows'],parts,ctx['curve'],level_to_volume);ctx['budgets']=rows
    ctx['stages'].append({'title':'日水量收支','rows':rows,'metrics':{'日账':len(rows),'完整日':sum(x['state']=='完整' for x in rows),'部分日':sum(x['state']=='部分' for x in rows),'缺测日':sum(x['state']=='缺测' for x in rows),'收支差 m³':str(sum((x['residual'] for x in rows if x['residual'] is not None),0))}});return ctx
