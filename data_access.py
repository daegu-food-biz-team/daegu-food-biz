"""Reads exact v2 handoff datasets; the legal-dong/admin-dong distinction is intentional."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
OFFICER = BASE / 'data' / 'officer_dongs.csv'
FOUNDER = BASE / 'data' / 'founder_cafe.csv'
MAP = BASE / 'data' / 'unit_hjd_map.csv'
HJD_GEO = BASE / 'geo' / 'daegu_hjd_ver20261001.geojson'
LEGAL_GEO = BASE / 'geo' / 'daegu_legal_dong.geojson'
REQUIRED_OFFICER = {'diagnosis_scope','unit','gu','dong','is_stagnant','bottleneck','confidence','val_accuracy','rule_agree','entry_pct','surv_pct','reasons','n_active','growth_past3','open_rate','close_rate','pop3','model_version','t0'}
REQUIRED_FOUNDER = {'unit','gu','dong','industry','surv2_adj','surv2_raw','cohort_n','small_sample','active_2025'}
REQUIRED_MAP = {'unit','hjd_code','stores','share','hjd_name'}

def read_files():
    o = pd.read_csv(OFFICER, encoding='utf-8-sig', dtype={'hjd_main_code':str,'unit':str})
    f = pd.read_csv(FOUNDER, encoding='utf-8-sig', dtype={'unit':str})
    m = pd.read_csv(MAP, encoding='utf-8-sig', dtype={'hjd_code':str,'unit':str})
    return validate(o,f,m)

def validate(o, f, m):
    for name, frame, required in [('officer_dongs',o,REQUIRED_OFFICER),('founder_cafe',f,REQUIRED_FOUNDER),('unit_hjd_map',m,REQUIRED_MAP)]:
        absent=required-set(frame.columns)
        if absent: raise ValueError(f'{name}: 필수 열 누락: {sorted(absent)}')
        if frame['unit'].isna().any(): raise ValueError(f'{name}: 빈 unit 키가 있습니다.')
    if o.unit.duplicated().any() or f.unit.duplicated().any(): raise ValueError('법정동 unit 중복이 있습니다.')
    if m[['unit','hjd_code']].duplicated().any(): raise ValueError('행정동 매핑 (unit, hjd_code)이 중복됩니다.')
    if not set(f.unit).issubset(set(o.unit)): raise ValueError('카페 데이터에 담당자 데이터와 불일치하는 unit이 있습니다.')
    diagnosed=o['diagnosis_scope'].eq('진단 (7개 구 정체 동)')
    rural=o['diagnosis_scope'].eq('현황만 (읍·면, 진단 범위 밖)')
    non_stagnant=o['diagnosis_scope'].eq('현황만 (정체 동 아님)')
    if not (diagnosed|rural|non_stagnant).all():
        raise ValueError('인식할 수 없는 diagnosis_scope가 있습니다.')
    if not o.loc[diagnosed,'is_stagnant'].eq(True).all():
        raise ValueError('진단 대상에는 is_stagnant=True가 필요합니다.')
    if not o.loc[non_stagnant,'is_stagnant'].eq(False).all():
        raise ValueError('정체 동이 아닌 7개 구에는 is_stagnant=False가 필요합니다.')
    if not o.loc[rural,'is_stagnant'].isna().all():
        raise ValueError('진단 범위 밖 읍·면의 is_stagnant는 비워야 합니다.')
    if o.loc[~diagnosed,['bottleneck','confidence','val_accuracy','entry_pct','surv_pct']].notna().any().any():
        raise ValueError('현황만 제공 지역에 병목 예측 지표가 있으면 안 됩니다.')
    if o.loc[diagnosed,['bottleneck','confidence','val_accuracy','entry_pct','surv_pct']].isna().any().any():
        raise ValueError('진단 대상의 병목/확신도/순위가 누락되었습니다.')
    if not set(o.loc[diagnosed,'bottleneck']).issubset({'진입 병목','생존 병목'}):
        raise ValueError('진단 대상에 알 수 없는 병목 유형이 포함되어 있습니다.')
    if not set(o.loc[diagnosed,'confidence']).issubset({'높음','보통','낮음'}):
        raise ValueError('확신도는 높음/보통/낮음 중 하나여야 합니다.')
    if not o.loc[rural,'gu'].isin({'달성군','군위군'}).all():
        raise ValueError('진단 범위 밖 읍·면은 달성군 또는 군위군만 허용합니다.')
    if not o.surv_pct.dropna().between(0,1).all() or not o.entry_pct.dropna().between(0,1).all():
        raise ValueError('모델 순위 값은 0~1 범위여야 합니다.')
    if not f.surv2_adj.dropna().between(0,1).all():
        raise ValueError('생존율 값은 0~1 범위여야 합니다.')
    return o, f, m

def connection_url():
    url=os.environ.get('DATABASE_URL','')
    if url:return url
    try:
        import streamlit as st
        return st.secrets.get('DATABASE_URL','')
    except Exception:
        return ''

def read_postgres(url):
    from sqlalchemy import create_engine, text
    engine=create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout':5})
    try:
        with engine.connect() as conn:
            o=pd.read_sql(text('SELECT * FROM mart.officer_latest ORDER BY unit'),conn)
            f=pd.read_sql(text('SELECT * FROM mart.founder_cafe_latest ORDER BY unit'),conn)
            m=pd.read_sql(text('SELECT * FROM mart.unit_hjd_latest ORDER BY unit,hjd_code'),conn)
        o['hjd_main_code']=o['hjd_main_code'].astype(str)
        m['hjd_code']=m['hjd_code'].astype(str)
        return validate(o,f,m)
    finally: engine.dispose()

def load_geometry():
    """Team legal polygons (if supplied), otherwise *administrative* preview polygons.
    Team legal geometry must carry properties.unit exactly matching '구 법정동'.
    """
    if LEGAL_GEO.is_file():
        geo=json.loads(LEGAL_GEO.read_text('utf-8'))
        if geo.get('type')!='FeatureCollection' or not geo.get('features'):
            raise ValueError('법정동 GeoJSON은 비어 있지 않은 FeatureCollection이어야 합니다.')
        if any('unit' not in (ft.get('properties') or {}) for ft in geo['features']):
            raise ValueError('법정동 GeoJSON 각 feature.properties.unit이 필요합니다. 임의 매칭 금지.')
        return geo,'legal'
    geo=json.loads(HJD_GEO.read_text('utf-8'))
    return geo,'admin-preview'

def map_features(officer,founder,mapping,geometry,geo_mode):
    """Do not silently render an administrative polygon as a legal-dong boundary."""
    o={r['unit']:r for r in officer.to_dict('records')}
    f={r['unit']:r for r in founder.to_dict('records')}
    candidates={}
    for r in mapping.to_dict('records'):
        candidates.setdefault(str(r['hjd_code']), []).append(r)
    display=[]; collisions=0; represented=set(); unresolved=[]
    for feat in geometry['features']:
        p=feat.get('properties',{})
        if geo_mode=='legal':
            unit=p.get('unit',''); unit_code=str(p.get('code') or p.get('EMD_CD') or '자료 미제공')
            physical=str(unit)
            overlapped=0
        else:
            code=str(p.get('adm_cd2',''))
            rows=sorted(candidates.get(code,[]),key=lambda x:(-float(x['stores']),str(x['unit'])))
            winner=rows[0] if rows else None
            unit=winner['unit'] if winner else ''
            unit_code=code
            physical=str(p.get('adm_nm',''))
            overlapped=max(0,len(rows)-1)
            if overlapped:collisions+=1
        if unit and unit not in o:unresolved.append(unit)
        if unit in o:represented.add(unit)
        props={'UNIT':str(unit) if unit in o else '',
               'CODE':unit_code,'PHYSICAL_NAME':physical,
               'OVERLAP':overlapped,'MAP_MODE':geo_mode,
               'HJD_LABEL':physical if geo_mode!='legal' else ''}
        display.append({'type':'Feature','geometry':feat['geometry'],'properties':props})
    return {'type':'FeatureCollection','features':display}, {'mapped_units':len(represented),'collisions':collisions,'unmatched_units':len(set(o)-represented),'invalid_unit_features':len(unresolved)}

def bound_extent(geo):
    x1,y1,x2,y2=180,90,-180,-90
    def traverse(obj):
        nonlocal x1,y1,x2,y2
        if not isinstance(obj,(list,tuple)) or not obj:return
        if isinstance(obj[0],(int,float)) and len(obj)>=2:
            lon,lat=obj[:2]
            x1=min(x1,lon);x2=max(x2,lon);y1=min(y1,lat);y2=max(y2,lat)
        else:
            for sub in obj:traverse(sub)
    for f in geo['features']:traverse(f['geometry'].get('coordinates',[]))
    return [[y1,x1],[y2,x2]]

def locate_unit(lon, lat, geo):
    """Find clicked feature in lat/lon coordinates (Shapely optional runtime)."""
    try:
        from shapely.geometry import shape,Point
        point=Point(lon,lat)
        for f in geo['features']:
            if shape(f['geometry']).covers(point):
                return f['properties'].get('UNIT','')
    except ImportError:
        return ''
    return ''
