def evaluate(rows,tolerance):
    result=[]
    for row in rows:
        if row['state']!='完整' or row['residual'] is None:code='GAP';state='待补测'
        elif abs(row['residual'])>tolerance:code='LIMIT';state='待复核'
        else:code='PASS';state='通过'
        result.append({**row,'code':code,'state':state})
    return result
