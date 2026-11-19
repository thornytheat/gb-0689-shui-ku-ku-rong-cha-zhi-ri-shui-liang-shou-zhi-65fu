from .rules import trace
from app.modules.m4_storage.service import level_to_volume
from decimal import Decimal as D
def execute(ctx):
    expected=sum((level_to_volume(p['right']['level'],ctx['curve'])-level_to_volume(p['left']['level'],ctx['curve']) for p in ctx['level_parts']),D(0))
    ctx['audit']=trace(ctx['records'],ctx['quarantine'],ctx['input_count'],ctx['flows'],ctx['budgets'],storage_expected=expected)
    rows=[{'station':k,'time':v} for k,v in sorted(ctx['audit']['watermarks'].items())]
    ctx['stages'].append({'title':'重算水位','rows':rows,'metrics':{'采信':len(ctx['records']),'隔离':len(ctx['quarantine']),'缺口':len(ctx['gaps'])+len(ctx['level_gaps']),'迟到测次':sum(r.get('arrival')=='迟到' for r in ctx['records'])}});return ctx
