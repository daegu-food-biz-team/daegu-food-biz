#!/usr/bin/env python3
"""Validate incoming CSV; optionally commit one atomic, versioned PostgreSQL batch.

--check                 Local schema/count/hash validation; never touches PostgreSQL.
--apply                 One transactional load into raw + latest marts.
--watch --interval 300  Poll file fingerprint; load only when changed (requires DB URL).
"""
from __future__ import annotations
import sys
import os
import argparse
import time
import json
import hashlib
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data_access import read_files,OFFICER,FOUNDER,MAP

DATASETS=[('officer_dongs',OFFICER,'mart.officer_latest'),
          ('founder_cafe',FOUNDER,'mart.founder_cafe_latest'),
          ('unit_hjd_map',MAP,'mart.unit_hjd_latest')]

def fingerprint():
    hash_=hashlib.sha256()
    for n,path,_ in DATASETS:
        hash_.update(n.encode('utf-8'));hash_.update(path.read_bytes())
    return hash_.hexdigest()

def serial(v):
    if isinstance(v,float) and pd.isna(v):return None
    if pd.isna(v):return None
    if hasattr(v,'item'):return v.item()
    return v

def apply(url, hash_, frames):
    import psycopg
    from psycopg import sql
    conn_url=url.replace('postgresql+psycopg://','postgresql://',1)
    # psycopg uses postgresql:// while SQLAlchemy/Streamlit uses postgresql+psycopg://
    if not conn_url.startswith('postgresql://'):
        raise ValueError('DATABASE_URL must begin with postgresql+psycopg:// or postgresql://')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+hash_[:12]
    with psycopg.connect(conn_url,connect_timeout=8) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute((ROOT/'db/schema.sql').read_text('utf-8'))
                cur.execute('SELECT run_id, content_hash FROM raw.ingestion_runs ORDER BY inserted_at DESC, run_id DESC LIMIT 1')
                old=cur.fetchone()
                if old and old[1] == hash_:
                    print('이미 최신 상태로 반영된 파일 해시:',old[0]);return False
                o,f,m=frames
                cur.execute('INSERT INTO raw.ingestion_runs (run_id,content_hash,source_description,officer_count,founder_count,mapping_count,model_version,as_of) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                            (run_id,hash_,'frontend_handoff delivery CSV',len(o),len(f),len(m),str(o.model_version.iloc[0]),int(o.t0.iloc[0])))
                for (name,_,_),frame in zip(DATASETS,frames):
                    # Retain raw payload, even after current mart is replaced.
                    rows=[(run_id,name,i+1,str(r['unit']),json.dumps({k:serial(v) for k,v in r.items()},ensure_ascii=False,allow_nan=False))
                          for i,r in enumerate(frame.to_dict('records'))]
                    cur.executemany('INSERT INTO raw.ingest_rows(run_id,dataset,row_number,unit,payload) VALUES (%s,%s,%s,%s,%s::jsonb)',rows)
                # All three current marts are replaced in one transaction. FK-safe order.
                for table in ['mart.unit_hjd_latest','mart.founder_cafe_latest','mart.officer_latest']:
                    sch,tab=table.split('.')
                    cur.execute(sql.SQL('DELETE FROM {}.{}').format(sql.Identifier(sch),sql.Identifier(tab)))
                for (_,_,table),frame in zip(DATASETS,frames):
                    sch,tab=table.split('.')
                    cols=list(frame.columns)
                    query=sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(
                         sql.Identifier(sch),sql.Identifier(tab),
                         sql.SQL(',').join(map(sql.Identifier,cols)),
                         sql.SQL(',').join([sql.Placeholder()]*len(cols)))
                    rows=[tuple(serial(r[c]) for c in cols) for r in frame.to_dict('records')]
                    cur.executemany(query,rows)
    print('반영 완료:',run_id,'/ officer',len(o),'founder',len(f),'map',len(m))
    return True

def check():
    frames=read_files()
    o,f,m=frames
    summary={'officer_count':len(o),'stagnant_count':int(o.diagnosis_scope.eq('진단 (7개 구 정체 동)').sum()),
       'out_of_scope_count':int(o.diagnosis_scope.eq('현황만 (읍·면, 진단 범위 밖)').sum()),
       'entry_count':int((o.bottleneck=='진입 병목').sum()),
       'survival_count':int((o.bottleneck=='생존 병목').sum()),
       'cafe_count':len(f),'mapping_rows':len(m),
       'model_version':str(o.model_version.iloc[0]),'as_of':int(o.t0.iloc[0]),
       'content_hash':fingerprint()}
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    return frames,summary['content_hash']

def main():
    parser=argparse.ArgumentParser(description='Validate / version / commit Data Warehouse inputs.')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--watch',action='store_true')
    parser.add_argument('--interval',type=int,default=300)
    args=parser.parse_args()
    if args.check:
        check();return
    url=os.environ.get('DATABASE_URL')
    if not url:raise SystemExit('DATABASE_URL을 환경 변수로 지정해야 PostgreSQL에 적재할 수 있습니다.')
    if args.apply:
        frames,hash_=check();apply(url,hash_,frames);return
    if args.interval<15:raise SystemExit('--interval은 15초 이상이어야 합니다.')
    print('파일 변경 감시 실행 (프로세스가 켜져 있을 때만 작동합니다). 종료: Ctrl+C')
    last=None
    try:
        while True:
            h=fingerprint()
            if h!=last:
                try:
                    frames=read_files();apply(url,h,frames);last=h
                except Exception as e:
                    print(f'검증 또는 적재 실패 ({type(e).__name__}): {e}',file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:print('감시 종료')

if __name__=='__main__':main()
