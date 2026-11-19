from app.pipeline import run
from app.config import SAMPLES
from app import store
from decimal import Decimal as D
def test_dirty_flow_reconciles(raw,isolate):
    result=run(raw)
    assert len(result["stages"])==7
    assert result["input_count"]==len(result["records"])+len(result["quarantine"])
def test_same_content_is_idempotent(raw,isolate):
    a=run(raw);b=run(raw)
    assert a["manifest"]["run_id"]==b["manifest"]["run_id"]
    assert a["manifest"]["created"]==b["manifest"]["created"]
def test_real_http_modules(client):
    for stage in range(1,8):
        reply=client.get(f"/api/m{stage}")
        assert reply.status_code==200
        assert len(reply.json["stages"])==stage
def test_invalid_csv_is_recoverable(client):
    result=client.post("/api/runs",json={"text":"bad,header\n1,2"})
    assert result.status_code==422
    assert result.json["code"]=="HEADER"
def test_real_pages_and_export(client):
    for stage in range(1,8): assert client.get(f"/m/{stage}").status_code==200
    response=client.get("/api/evidence.csv")
    assert response.status_code==200 and "原因码" in response.text
def test_stale_review_rejected(client):
    r=client.post("/api/runs",json={}).json
    body={"version":r["version"],"decision":"通过"}
    assert client.post("/api/review/"+r["manifest"]["run_id"],json=body).status_code==200
    assert client.post("/api/review/"+r["manifest"]["run_id"],json=body).status_code==409

HEADER="id,station,time,level,inflow,outflow,flow_unit,version\n"
def day_csv(flow_hours):
    # 水位00:00-24:00每小时一路;流量只到flow_hours时(模拟小时路迟到)
    from datetime import datetime,timedelta
    base=datetime(2026,11,18);stamp=lambda i:(base+timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S")+"+08:00"
    lines=[]
    for i in range(25):
        lines.append(f"L{i:03d},青岚库,{stamp(i)},{101+0.01*i:.2f},,,,1")
    for i in range(flow_hours+1):
        lines.append(f"F{i:03d},青岚库,{stamp(i)},,2.0,1.5,m3/s,1")
    return HEADER+"\n".join(lines)
def day_row(result):
    return next(x for x in result["budgets"] if x["date"]=="2026-11-18")

def test_shift_handover_with_partial_flow(isolate):
    # 流量只到08:00,当天08:00班次仍可交班:结果给出且注明各自依据时段
    day=day_row(run(day_csv(8)))
    assert day["state"]=="部分"
    assert D(day["flow_hours"])==8 and D(day["level_hours"])==24 and D(day["compare_hours"])==8
    assert day["flow_windows"]==[["2026-11-18T00:00:00+08:00","2026-11-18T08:00:00+08:00"]]
    assert day["level_windows"]==[["2026-11-18T00:00:00+08:00","2026-11-19T00:00:00+08:00"]]
    assert D(day["in_m3"])==D("2.0")*8*3600

def test_backfill_rerun_never_double_counts(isolate):
    # 先按已到数据交班,后补数据重跑同一天:整日重算而非累加,旧批次与依据保留
    first=run(day_csv(8));first_id=first["manifest"]["run_id"]
    second=run(day_csv(24));second_id=second["manifest"]["run_id"]
    assert first_id!=second_id
    day=day_row(second)
    assert day["state"]=="完整" and D(day["in_m3"])==D("2.0")*24*3600
    assert D(day["in_m3"])!=D(day_row(first)["in_m3"])+D("2.0")*24*3600  # 没有新旧叠加
    kept=day_row(store.fetch(first_id))  # 旧交班批次仍在,依据时段未丢
    assert kept["state"]=="部分" and D(kept["flow_hours"])==8 and kept["flow_windows"]
    again=run(day_csv(24))  # 相同内容重跑复用同一批次
    assert again["manifest"]["run_id"]==second_id

def test_duplicate_rows_never_double_count(isolate):
    text=day_csv(24);doubled=text+"\n"+"\n".join(text.split("\n")[1:])
    a,b=day_row(run(text)),day_row(run(doubled))
    assert D(a["in_m3"])==D(b["in_m3"]) and D(a["storage_change"])==D(b["storage_change"])

def test_two_stream_sample(isolate):
    # 水位30分钟一路、流量整点过20分一路,两路错开仍各自入账
    result=run((SAMPLES/"streams.csv").read_bytes())
    assert result["input_count"]==len(result["records"])+len(result["quarantine"])
    day=day_row(result)
    assert day["state"]=="部分" and D(day["level_hours"])==24
    assert D(day["flow_hours"])==D(71)/3 and day["flow_windows"]==[["2026-11-18T00:20:00+08:00","2026-11-19T00:00:00+08:00"]]
    assert sum(r.get("arrival")=="迟到" for r in result["records"])>=1
