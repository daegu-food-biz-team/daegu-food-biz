"""DAEGU FOOD BIZ · HTML/SVG interface hosted at the existing Streamlit Cloud URL.
The local SVG map handles clicks without rerunning Streamlit; CSV/GeoJSON
inputs refresh when files change. PostgreSQL/LLM are not yet connected.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from data_access import read_files, load_geometry, map_features, bound_extent

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='DAEGU FOOD BIZ · 대구 외식 상권',page_icon='◼',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{background:#fafafa!important;color:#111214!important}
#MainMenu,footer[data-testid="stFooter"],header[data-testid="stHeader"],[data-testid="stDecoration"],[data-testid="stToolbar"],.stAppDeployButton{visibility:hidden!important;height:0!important;min-height:0!important}
[data-testid="stMainBlockContainer"],.block-container{max-width:100%!important;padding:0!important;margin:0!important}
[data-testid="stVerticalBlock"]{gap:0!important}
[data-testid="stIFrame"],iframe{border:0!important;border-radius:0!important}
[data-testid="stAppViewContainer"]{overflow-x:hidden!important}
</style>''',unsafe_allow_html=True)

def file_signature():
    paths=[ROOT/'data/officer_dongs.csv',ROOT/'data/founder_cafe.csv',ROOT/'data/unit_hjd_map.csv',ROOT/'geo/daegu_hjd_ver20261001.geojson',ROOT/'llm/report_input_example.json',ROOT/'preview_quick_open.html']
    return tuple((str(p.relative_to(ROOT)),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)

@st.cache_data(show_spinner=False)
def html_from_sources(signature):
    html=(ROOT/'preview_quick_open.html').read_text(encoding='utf-8')
    officer,founder,mapping=read_files()
    geometry,mode=load_geometry()
    geo,stats=map_features(officer,founder,mapping,geometry,mode)
    def rows(df):
        return [{k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in d.items()} for d in df.to_dict('records')]
    payload={'officer':rows(officer),'founder':rows(founder),'geo':geo,'bounds':bound_extent(geo),'stats':stats,'examples':json.loads((ROOT/'llm/report_input_example.json').read_text('utf-8')),'geomMode':mode}
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e')
    start=html.index('const DATA=')
    stop=html.index(';\nconst off=',start)
    return html[:start]+'const DATA='+encoded+html[stop:]

try:
    html=html_from_sources(file_signature())
except Exception as exc:
    st.error('전달 데이터 또는 화면을 불러오지 못했습니다.')
    st.code(f'{type(exc).__name__}: {exc}')
    st.stop()

# Streamlit>=1.67 auto-sizes the iframe to its HTML content.
# Browser-side map clicks update panels without rerunning/remounting the map.
st.iframe(html,width='stretch',height='content',alt='대구 외식 상권 내비게이터: 동별 병목 진단 및 창업자 분석')
