"""DAEGU FOOD BIZ v0.7 – v0.3 look, handed-off v2 data, rigorous map semantics."""
from __future__ import annotations
import json
import os
from pathlib import Path
from html import escape
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from streamlit_folium import st_folium

from data_access import (BASE,read_files,read_postgres,connection_url,load_geometry,
                         map_features,locate_unit)
from map_views import (build_map,ENTRY,SURV,FOUNDER_COLORS,GRAY,OUT_SCOPE,NO_DATA,status_label)

st.set_page_config(page_title='DAEGU FOOD BIZ · 대구 외식 상권',page_icon='◼',layout='wide',initial_sidebar_state='collapsed')
# Self-contained cloud hotfix: only app.py needs replacement on GitHub.
# Keep the original editorial stylesheet unchanged; append targeted overrides.
CLOUD_FIX_CSS = r"""
/* v0.8 cloud fix: readable native selectors, HTML-prototype-like compact nav. */
[data-testid="stSelectbox"] label,
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"],
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p,
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] span {
  color:#555C65!important;opacity:1!important;font-weight:650!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"]>div,
[data-testid="stSelectbox"] [data-baseweb="select"] [role="combobox"] {
  color:#17191C!important;background-color:#FFFFFF!important;
  border-color:#C9CDD3!important;opacity:1!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] input,
[data-testid="stSelectbox"] [role="combobox"] *,
[data-testid="stSelectbox"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p {
  color:#17191C!important;opacity:1!important;-webkit-text-fill-color:#17191C!important;
}
/* Normal buttons, not theme-colored segmented controls; preserve HTML active-black nav. */
[class*="st-key-nav_button_"] button {
  background:#FFFFFF!important;color:#1C1D20!important;border:1px solid #B7BBC1!important;
  min-height:36px!important;padding:5px 7px!important;border-radius:0!important;
  font-weight:750!important;font-size:12px!important;white-space:nowrap!important;
}
[class*="st-key-nav_button_"] button[kind="primary"] {
  background:#1B1C1F!important;color:#FFFFFF!important;border-color:#1B1C1F!important;
}
[class*="st-key-nav_button_"] button:hover {
  background:#F3F4F5!important;color:#151619!important;border-color:#1B1C1F!important;
}
[class*="st-key-nav_button_"] button[kind="primary"]:hover {
  background:#33353A!important;color:#FFFFFF!important;border-color:#33353A!important;
}
[class*="st-key-nav_button_"] button p,
[class*="st-key-nav_button_"] button span { color:inherit!important; }
@media(max-width:700px){
  [class*="st-key-nav_button_"] button{font-size:10px!important;padding:5px 2px!important;min-height:32px!important;}
}

/* v0.9: restore the clear HTML-prototype form controls; fixes washed-out cloud text. */
[data-testid="stSelectbox"],
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stSelectbox"] [role="combobox"],
[data-testid="stSelectbox"] [role="combobox"] *,
[data-testid="stSelectbox"] [aria-selected],
[data-testid="stSelectbox"] input {
  color:#16191d!important;
  -webkit-text-fill-color:#16191d!important;
  opacity:1!important;
  filter:none!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"]>div,
[data-testid="stSelectbox"] [role="combobox"]{
  background-color:#fff!important;
  border-color:#b6bec7!important;
  min-height:42px!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] svg{color:#1c1f22!important;fill:#1c1f22!important;opacity:1!important;}
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] *,
[data-testid="stSelectbox"] label p{color:#4e5660!important;-webkit-text-fill-color:#4e5660!important;opacity:1!important;}
/* The top breadcrumb shares the vertical center of navigation, HTML-style. */
.dfb-nav-overline{display:flex;align-items:center;min-height:39px;
 color:#68707a;font-size:11px;font-weight:800;letter-spacing:.16em;}
.page-lead{padding-top:0!important;padding-bottom:4px!important;}
.page-lead h1{margin-top:1px!important;margin-bottom:3px!important;}
.page-lead p{margin:3px 0 1px!important;}
/* Sophisticated motion matching the HTML prototype, only on entering home. */
@keyframes dfb-home-reveal{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:translateY(0)}}
.initial-entry .hero{animation:dfb-home-reveal .78s cubic-bezier(.20,.72,.18,1) both!important;}
.initial-entry .hero h1,.initial-entry .hero p{animation:none!important;}
.animate-on-entry{animation:dfb-home-reveal .8s .24s cubic-bezier(.20,.72,.18,1) both!important;}
@media(prefers-reduced-motion:reduce){.initial-entry .hero,.animate-on-entry{animation:none!important;}}
@media(max-width:850px){.dfb-nav-overline{font-size:9px;letter-spacing:.10em;min-height:34px;}}

"""
st.markdown('<style>'+ (BASE/'assets/style.css').read_text('utf-8')+CLOUD_FIX_CSS+'</style>',unsafe_allow_html=True)

@st.cache_data(ttl=60,show_spinner=False)
def get_data(db_url):
    if db_url:
        try:return (*read_postgres(db_url),'PostgreSQL','')
        except Exception as err:
            files=read_files()
            return (*files,'동봉 CSV',f'PostgreSQL 연결 실패 ({type(err).__name__}). 동봉 CSV를 대신 표시합니다.')
    return (*read_files(),'동봉 CSV','')

@st.cache_data(ttl=60,show_spinner=False)
def get_geometry():
    return load_geometry()

try:
    officer_data,founder_data,mapping_data,source,connection_warning=get_data(connection_url())
    geometry,geom_mode=get_geometry()
    display_geo,map_coverage=map_features(officer_data,founder_data,mapping_data,geometry,geom_mode)
except Exception as error:
    st.error(f'전달 데이터 로딩 또는 검사 실패: {error}')
    st.info('README.md에 적힌 파일 구조와 각 CSV 컬럼을 확인해 주세요. 검증되지 않은 데이터는 지도에 표시하지 않습니다.')
    st.stop()

O={r['unit']:r for r in officer_data.to_dict('records')}
F={r['unit']:r for r in founder_data.to_dict('records')}
ALL_UNITS=sorted(O)
GUS=sorted(officer_data['gu'].dropna().unique())
REPORT_EXAMPLES={r['unit']:r for r in json.loads((BASE/'llm/report_input_example.json').read_text('utf-8'))}
POLICY_RULES=(BASE/'llm/report_rules.md').read_text('utf-8')
if 'view' not in st.session_state:st.session_state.view='home'
if 'selected_unit' not in st.session_state:st.session_state.selected_unit='중구 동성로2가' if '중구 동성로2가' in O else ALL_UNITS[0]
if 'gu' not in st.session_state:st.session_state.gu='대구 전체'
if 'officer_layer' not in st.session_state:st.session_state.officer_layer='병목 유형 · 확신도'
if 'founder_mode' not in st.session_state:st.session_state.founder_mode='카페·디저트 분석'
if 'report_source' not in st.session_state:st.session_state.report_source='officer'
if 'report_output' not in st.session_state:st.session_state.report_output=None
if 'first_visit' not in st.session_state:st.session_state.first_visit=True
if 'map_last_click' not in st.session_state:st.session_state.map_last_click=None

PAGE_LABELS={'home':'처음으로','officer':'담당자용','founder':'창업자용'}
LABEL_PAGES={v:k for k,v in PAGE_LABELS.items()}

def remember_page(page):
    # One stable top navigation; returning home deliberately replays the intro.
    if page==st.session_state.view:
        return False
    st.session_state.view=page
    if page=='home':
        st.session_state.first_visit=True
    return True

def go(page):
    if remember_page(page):
        st.rerun()

def header(page):
    right={'home':'ROLE SELECT','officer':'01 / DISTRICT DIAGNOSIS','founder':'02 / FOUNDER ANALYTICS','report':'03 / DISTRICT REPORT'}[page]
    st.markdown(f'<div class="site-header"><div><span class="brand-kor">대구 외식 상권 내비게이터</span><i class="brand-divider"></i><span class="brand-eng">DAEGU F&amp;B<br>COMMERCIAL NAVIGATOR</span></div><span class="header-right">{right}</span></div>',unsafe_allow_html=True)

def nav(page):
    # Match HTML: the section overline sits level with the center of the top buttons.
    index={'officer':'01','founder':'02','report':'03'}.get(page,'')
    label=f'{index} / DAEGU FOOD BIZ' if index else ''
    left_column,nav_column=st.columns([.67,.33],gap='small',vertical_alignment='center')
    with left_column:
        st.markdown(f'<div class="dfb-nav-overline">{label}</div>',unsafe_allow_html=True)
    with nav_column:
        nav_cols=st.columns([1,1,1],gap='small')
        current=page if page!='report' else st.session_state.report_source
        for col,(name,route) in zip(nav_cols,[('처음으로','home'),('담당자용','officer'),('창업자용','founder')]):
            with col:
                if st.button(name,type='primary' if current==route else 'secondary',
                             key=f'nav_button_{route}',use_container_width=True):
                    go(route)
    if page=='report':
        st.caption(f'처음으로 / {PAGE_LABELS.get(st.session_state.report_source,"담당자용")} / {st.session_state.selected_unit} / 진단 리포트')


def page_lead(index,title,subtitle,horizontal=False):
    klass='page-lead page-lead-horizontal' if horizontal else 'page-lead'
    st.markdown(f'<div class="{klass}"><div class="page-lead-flex"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div></div>',unsafe_allow_html=True)

def fmt_pct(val,digits=1):
    return '—' if pd.isna(val) else f'{float(val)*100:+.{digits}f}%'

def fmt_undirected(val,digits=1):
    return '—' if pd.isna(val) else f'{float(val)*100:.{digits}f}%'

def fmt_num(val):
    return '—' if pd.isna(val) else f'{int(val):,}'

def box_tag(status):
    css='entry' if status=='진입 병목' else 'survival' if status=='생존 병목' else 'ok' if status.startswith('정체 동 아님') else 'unknown'
    return f'<span class="signal {css}">{escape(status)}</span>'

def landing():
    header('home')
    intro_class='initial-entry' if st.session_state.first_visit else ''
    st.markdown(f'''<div class="{intro_class}"><div class="hero"><h1>DAEGU<br>FOOD BIZ</h1><p>대구 외식 상권의 현황을 진단하고,<br>입지와 생존 전략을 제안하는 데이터 기반 의사결정 플랫폼입니다.</p></div></div>''',unsafe_allow_html=True)
    st.write('')
    role_class='role animate-on-entry' if st.session_state.first_visit else 'role'
    s,a,b=st.columns([.49,.51,.51],gap='large')
    with a:
        st.markdown(f'<div class="{role_class}"><div class="eyebrow">FOR OPERATORS</div><div class="role-head">상권 담당자용</div><div class="role-desc">지역별 상권을 진단하고 정책 방향을 확인하세요.</div></div>',unsafe_allow_html=True)
        if st.button('진단 지도 열기  ↗',type='primary',use_container_width=True,key='landing_officer'):go('officer')
    with b:
        st.markdown(f'<div class="{role_class}"><div class="eyebrow">FOR FOUNDERS</div><div class="role-head">예비 창업자용</div><div class="role-desc">관심 업종의 상권을 분석하고, 입지 결정을 지원받으세요.</div></div>',unsafe_allow_html=True)
        if st.button('업종 분석 열기  ↗',use_container_width=True,key='landing_founder'):go('founder')
    st.markdown('<div class="small-footer">DAEGU FOOD BIZ · FOOD SERVICE DISTRICT INTELLIGENCE<br>점포 인허가 기반 분석 자료이며, 매출 예측이나 개별 점포 성공 보장은 아닙니다.</div>',unsafe_allow_html=True)
    st.session_state.first_visit=False

def data_status():
    if connection_warning:st.warning(connection_warning)
    with st.expander('자료 출처 · 데이터 상태',expanded=False):
        st.write(f'**자료 기준:** 2025년 말 / 모델 버전: {officer_data.model_version.iloc[0]}')
        st.write(f'**자료:** 총 {len(O)}개 지역 (7개 구 법정동 130곳 + 달성군·군위군 읍·면 14곳)')
        st.write(f'**병목 진단:** 7개 구의 정체 동 {int(officer_data.diagnosis_scope.eq("진단 (7개 구 정체 동)").sum())}곳 · 생존 병목 {int((officer_data.bottleneck=="생존 병목").sum())}곳 · 진입 병목 {int((officer_data.bottleneck=="진입 병목").sum())}곳')
        st.write('**달성군·군위군:** 과거 현황·카페 분석만 제공. 병목 진단/확신도 없음 (모델 검증 범위 밖).')
        st.write('**자료 연결:** '+source)
        st.write('**지도 경계:** '+('팀 제공 법정동 GeoJSON' if geom_mode=='legal' else '2026-10-01 버전 행정동 GeoJSON (법정동 경계 수령 전 임시)'))
        st.caption('법정동과 행정동을 동일하게 간주할 수 없습니다. 임시 행정동 지도의 색상은 폴리곤마다 음식점 기록 수가 가장 많은 대응 법정동 1곳의 결과만 나타냅니다.')
        if st.button('데이터 다시 조회',key='refresh_data'):
            get_data.clear();get_geometry.clear();st.rerun()

def unit_picker_changed():
    """Read widget value in its callback; do not set a rendered widget key."""
    st.session_state.selected_unit=st.session_state.unit_picker


def filters(role):
    # Selected district is independent of the Streamlit selectbox widget's key.
    # This allows a map click (later in the same run) to change the selected unit
    # without StreamlitWidgetAlreadyInstantiatedError.
    if role=='officer':
        c0,c1,c2,space=st.columns([2.9,2.1,2.8,7.2],gap='small',vertical_alignment='bottom')
        with c0:
            st.selectbox('지도 레이어',['병목 유형 · 확신도','3년 점포 증감 · 현황(예측 아님)'],key='officer_layer')
    else:
        c1,c2,space=st.columns([2.1,2.8,9.9],gap='small',vertical_alignment='bottom')
    with c1:
        selected_gu=st.selectbox('구·군 선택',['대구 전체']+GUS,key='gu')
    options=[u for u in ALL_UNITS if selected_gu=='대구 전체' or O[u]['gu']==selected_gu]
    if st.session_state.selected_unit not in options:
        st.session_state.selected_unit=options[0]
    # Assign unit_picker only before its widget is instantiated in this run.
    if st.session_state.get('unit_picker') != st.session_state.selected_unit:
        st.session_state.unit_picker=st.session_state.selected_unit
    with c2:
        st.selectbox('법정동·읍면 선택',options,key='unit_picker',on_change=unit_picker_changed)


def map_area(role):
    st.markdown('<div class="map-title">DAEGU · DISTRICT MAP</div>',unsafe_allow_html=True)
    if st.session_state.gu!='대구 전체':
        st.caption(f'{st.session_state.gu} 범위만 표시 · 화면에 맞춰 확대 · +/− 버튼 또는 마우스 휠로 확대/축소')
    desc=('확정 법정동 경계' if geom_mode=='legal' else '행정동 경계 기반 임시 미리보기 · 법정동 경계 수령 후 정확히 교체')
    st.markdown(f'<div class="map-sub">{desc} · 지도 위에서 선택하거나 목록에서 법정동을 찾으세요.</div>',unsafe_allow_html=True)
    lm='status' if st.session_state.officer_layer.startswith('3년') else 'diagnosis'
    # Build once per map scope and layer. Do not feed selected_unit into Folium HTML:
    # otherwise a click changes generated HTML and flashes/remounts the Leaflet iframe.
    # Selected unit remains available to panels and dropdown; JS handles outline on map click.
    data_sig=(len(officer_data),len(founder_data),geom_mode,
              int(pd.util.hash_pandas_object(officer_data[['unit','n_active','growth_past3']],index=False).sum()))
    cache_key=(role,lm,st.session_state.gu,data_sig)
    map_cache=st.session_state.setdefault('_dfb_map_cache',{})
    if cache_key not in map_cache:
        if len(map_cache)>5:map_cache.clear()
        map_cache[cache_key]=build_map(display_geo,officer_data,founder_data,
                                       role,lm,'',st.session_state.gu)
    fmap,visible=map_cache[cache_key]
    click=st_folium(fmap,height=530,key=f'realmap_{role}_{lm}_{st.session_state.gu}',
                    use_container_width=True,returned_objects=['last_object_clicked','last_clicked'])
    obj=click.get('last_object_clicked') if isinstance(click,dict) else None
    obj=obj or (click.get('last_clicked') if isinstance(click,dict) else None)
    if isinstance(obj,dict) and 'lat' in obj and 'lng' in obj:
        here=(round(float(obj['lat']),6),round(float(obj['lng']),6),role,lm,st.session_state.gu)
        if st.session_state.map_last_click!=here:
            st.session_state.map_last_click=here
            chosen=locate_unit(obj['lng'],obj['lat'],visible)
            if chosen and chosen in O and chosen!=st.session_state.selected_unit:
                st.session_state.selected_unit=chosen
                st.rerun()
    if geom_mode!='legal':
        st.markdown(f'<div class="dfb-quick-note">임시 지도: 144개 지역의 실제 현황값은 오른쪽 패널과 선택 목록에 모두 연결되어 있어요. 다만 현재 행정동 경계 150개 중 {map_coverage["collisions"]}개에서 복수 법정동이 겹쳐 대표 지역 1곳만 색칠됩니다. 법정동 경계가 오면 이 왜곡 없이 교체합니다.</div>',unsafe_allow_html=True)
    if role=='officer':
        if st.session_state.officer_layer.startswith('3년'):
            names=[('−10% 미만','#B94C54'),('−10% ~ −3%','#E3A5A5'),('−3% ~ +3%','#E9ECEF'),('+3% ~ +10%','#A6BEDB'),('+10% 이상','#3865A9')]
            legend=''.join(f'<span class="layer-legend-item"><i class="legend-color" style="background:{c}"></i>{escape(n)}</span>' for n,c in names)
            st.markdown('<div class="layer-legend">'+legend+'</div><div class="map-caption">최근 3년 점포 증감률은 과거 현황이며 미래 예측이나 지원 우선순위 점수가 아닙니다.</div>',unsafe_allow_html=True)
        else:
            legend=''.join(f'<span class="layer-legend-item"><i class="legend-color" style="background:{d[c]}"></i>{t} · {c}</span>' for t,d in [('진입 병목',ENTRY),('생존 병목',SURV)] for c in ['높음','보통','낮음'])
            legend += f'<span class="layer-legend-item"><i class="legend-color" style="background:{GRAY}"></i>정체 동 아님</span>'
            legend += f'<span class="layer-legend-item"><i class="legend-color" style="background:{OUT_SCOPE}"></i>읍·면 · 진단 범위 밖</span>'
            st.markdown('<div class="layer-legend">'+legend+'</div>',unsafe_allow_html=True)
            st.markdown('''<section class="legend-guide" aria-label="병목 색상 설명">
            <div class="legend-guide-heading">지도 색상 안내 <span>HOW TO READ THE MAP</span></div>
            <div class="legend-guide-grid">
              <div class="legend-guide-item"><i class="swatch" style="background:#1F4FB8"></i><div><strong>진입 병목 · 파랑</strong><p>정체 동 가운데 생존에 비해 신규 음식점 진입이 상대적으로 부족한 유형입니다.</p></div></div>
              <div class="legend-guide-item"><i class="swatch" style="background:#C65A11"></i><div><strong>생존 병목 · 주황</strong><p>정체 동 가운데 신규 진입에 비해 개업 후 생존이 상대적으로 취약한 유형입니다.</p></div></div>
              <div class="legend-guide-item"><i class="swatch" style="background:#7898D6"></i><div><strong>진하기 = 확신도</strong><p>진할수록 확신도 높음(과거 적중 82%), 중간 73%, 옅음 52%. 개별 동의 성공 확률이 아닙니다.</p></div></div>
              <div class="legend-guide-item"><i class="swatch" style="background:#DDE0E4"></i><div><strong>연회색 · 정체 동 아님</strong><p>7개 구의 정체 동이 아니며 현황 지표만 제공합니다.</p></div></div>
              <div class="legend-guide-item"><i class="swatch" style="background:#A7B0BB"></i><div><strong>진회색 · 진단 범위 밖</strong><p>달성군·군위군 읍·면은 병목 예측 없이 과거 현황·카페 통계만 제공합니다.</p></div></div>
            </div></section>''',unsafe_allow_html=True)
    else:
        lab=['58% 미만','58~63%','63~69%','69~73%','73% 이상']
        legend=''.join(f'<span class="layer-legend-item"><i class="legend-color" style="background:{col}"></i>{x}</span>' for x,col in zip(lab,FOUNDER_COLORS))
        st.markdown('<div class="layer-legend">'+legend+'<span class="layer-legend-item">▨ 표본 20건 미만: 빗금</span></div>',unsafe_allow_html=True)
        st.caption('색상은 카페·디저트 개업 후 2년 생존율(표본 보정값)입니다. 분석 단위와 경계 단위가 일치하지 않는 임시 지도임에 유의해 주세요.')

def officer_panel():
    u=st.session_state.selected_unit
    rec=O[u];stat=status_label(rec)
    conf=rec.get('confidence');acc=rec.get('val_accuracy')
    rank_html=''
    if rec['diagnosis_scope'].startswith('진단') and pd.notna(rec.get('entry_pct')) and pd.notna(rec.get('surv_pct')):
        entry_percent=max(0.0,min(100.0,100*float(rec['entry_pct'])))
        survival_percent=max(0.0,min(100.0,100*float(rec['surv_pct'])))
        entry_top=max(1,round(100-entry_percent))
        survival_top=max(1,round(100-survival_percent))
        rank_html=f'''<div class="district-ranks"><div class="rank-heading">대구 정체 동 65곳 중 상대 순위</div>
          <div class="rank-item"><div class="rank-label"><span>진입 활력</span><strong>상위 {entry_top}%</strong></div><div class="rank-track"><div class="rank-fill entry" style="width:{entry_percent:.1f}%"></div></div></div>
          <div class="rank-item"><div class="rank-label"><span>생존 안정</span><strong>상위 {survival_top}%</strong></div><div class="rank-track"><div class="rank-fill survival" style="width:{survival_percent:.1f}%"></div></div></div>
          <div class="rank-note">정체 동 내 상대 비교입니다. 높은 순위가 성공 확률이나 정책 지원 우선순위를 의미하지 않습니다.</div></div>'''
    st.markdown('<div class="map-title">REGION INSIGHT</div><div class="map-sub">선택한 지역의 검증된 분석 수치</div>',unsafe_allow_html=True)
    st.markdown(f'''<div class="detail-panel"><div class="detail-overline">SELECTED DISTRICT / 2025</div>
    <div class="detail-title">{escape(str(rec['dong']))}</div><div class="detail-meta">대구광역시 {escape(rec['gu'])} · {escape(u)}</div>
    <div style="margin-top:15px">{box_tag(stat)}</div>
    <div class="metric-row" style="margin-top:15px"><div><span>영업 중 외식 점포</span><div class="metric-big">{fmt_num(rec['n_active'])}</div></div><div><span>최근 3년 점포 증감 · 현황</span><div class="metric-big" style="font-size:25px">{fmt_pct(rec['growth_past3'])}</div></div></div>
    <div class="metric-row"><div><span>3년 개업 건수 / 현재 점포 수</span><br><strong>{fmt_undirected(rec['open_rate'])}</strong></div><div><span>3년 폐업 건수 / 현재 점포 수</span><br><strong>{fmt_undirected(rec['close_rate'])}</strong></div></div>
    <div class="metric-row"><div><span>3년 인구 증감</span><br><strong>{fmt_pct(rec['pop3'])}</strong></div><div><span>자료 구분</span><br><strong>{'진단 + 현황' if rec['diagnosis_scope'].startswith('진단') else '과거 현황만'}</strong></div></div>
    {rank_html}</div>''',unsafe_allow_html=True)
    if rec['diagnosis_scope'].startswith('진단'):
        st.markdown(f'**확신도: {conf}** · 과거 동일 구간 적중률 **{fmt_undirected(acc,0)}**')
        st.caption('과거 평가 결과이며, 이 동에 대한 예측 확률이나 정책 지원 우선순위가 아닙니다.')
        if rec.get('rule_agree') is False or rec.get('rule_agree')==False:
            st.warning('현장 확인 우선: 모델 판정과 단순 폐업률 규칙의 방향이 다릅니다.')
        if isinstance(rec.get('reasons'),str):
            st.markdown('**진단에 작용한 주요 변수**')
            st.caption(' · '.join(x.strip() for x in rec['reasons'].split(',') if x.strip()))
        if st.button('이 동의 진단 리포트 보기  ↗',type='primary',use_container_width=True,key='to_report'):
            st.session_state.report_source='officer';st.session_state.report_output=None;go('report')
    else:
        st.info('진단 범위 밖인 달성군·군위군 읍·면은 병목 예측과 확신도를 제공하지 않습니다. 아래의 과거 현황 자료만 참고해 주세요.' if rec['diagnosis_scope'].startswith('현황만 (읍·면') else '7개 구의 정체 동이 아니므로 병목 진단 없이 과거 현황만 확인합니다.')


def officer():
    header('officer');nav('officer')
    page_lead('01','동별 병목 진단','7개 구 정체 동 65곳의 병목 진단 · 144개 지역의 과거 현황 조회')
    filters('officer')
    left,right=st.columns([1.78,.94],gap='large')
    with left:map_area('officer')
    with right:officer_panel()
    st.caption('모델 기준: 2025년 말 정체 동 65곳 상대 평가. 과거 병목 유형 적중률 70%로 단순 폐업률 규칙보다 성능이 높다고 볼 수 없습니다. 지원 우선순위는 모델이 결정하지 않습니다.')
    data_status()

def cafe_chart(rec):
    years=list(range(2016,2026))
    opening=[rec[f'open_{year}'] for year in years]
    closing=[rec[f'close_{year}'] for year in years]
    fig=go.Figure()
    fig.add_bar(x=[str(y) for y in years],y=opening,name='개업',marker_color='#287A58')
    fig.add_bar(x=[str(y) for y in years],y=closing,name='폐업',marker_color='#B65359')
    fig.update_layout(barmode='group',height=220,margin=dict(l=8,r=8,t=10,b=5),
         paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(size=10,color='#555e68'),
         xaxis=dict(type='category',showgrid=False),yaxis=dict(gridcolor='#e8eaee',zeroline=False),
         legend=dict(orientation='h',y=1.24,x=0))
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

def founder_panel():
    rec=F.get(st.session_state.selected_unit)
    st.markdown('<div class="map-title">CAFE · LOCAL PROFILE</div><div class="map-sub">카페·디저트 · 개업 후 2년 생존율 분석</div>',unsafe_allow_html=True)
    if not rec:
        st.info('해당 법정동의 카페 자료가 없습니다.');return
    adjusted=fmt_undirected(rec['surv2_adj'])
    warn='<div class="danger-note">표본 20건 미만 · 보정값의 해석에 주의</div>' if rec['small_sample'] else ''
    st.markdown(f'''<div class="detail-panel"><div class="detail-overline">FOUNDER INSIGHT</div>
      <div class="detail-title">{escape(rec['dong'])}</div><div class="detail-meta">대구광역시 {escape(rec['gu'])} · 카페·디저트</div>
      <div class="metric-row" style="margin-top:15px"><div><span>개업 후 2년 생존율 · 보정</span><div class="metric-big metric-blue">{adjusted}</div></div></div>
      <div class="metric-row"><div><span>관찰 코호트</span><br><strong>{fmt_num(rec['cohort_n'])}개 카페</strong></div><div><span>2025년 말 영업 중</span><br><strong>{fmt_num(rec['active_2025'])}개</strong></div></div>
      <div class="metric-row"><div><span>2022년 말 영업 중</span><br><strong>{fmt_num(rec['active_2022'])}개</strong></div><div><span>참고 대구 평균</span><br><strong>66.4%</strong></div></div>{warn}</div>''',unsafe_allow_html=True)
    st.markdown('<div class="section-line"><div class="map-title">ANNUAL MOVEMENT</div><div class="map-sub">2016–2025년 개업·폐업 기록</div></div>',unsafe_allow_html=True)
    cafe_chart(rec)
    st.caption('2015~2023년 개업 카페의 개업 후 2년 생존율이며, 소표본은 대구 평균 쪽으로 보정한 값입니다.')

def spot_history():
    st.markdown('<div class="map-title">SITE HISTORY / PLACE TRACKER</div>',unsafe_allow_html=True)
    st.info('자리 이력 원자료는 아직 받지 않았습니다. 현재 파일에는 개별 주소·층·호수·점포별 인허가 이력이 없어 실제 자리 이력 조회를 제공할 수 없습니다.')
    address=st.text_input('주소 입력 · 데이터 연결 대기',placeholder='대구광역시 ○○구 ○○로 00, 1층 101호')
    if address:st.warning('현재 이 주소로 조회할 수 있는 데이터가 없습니다. 실제 주소를 입력해도 가상의 결과를 표시하지 않습니다.')
    st.caption('향후: 인허가일·폐업일·사업장명·정규화 주소·층·호수로 조회. 같은 주소와 같은 점포는 별도 판정합니다.')

def founder():
    header('founder');nav('founder')
    page_lead('02','업종별 동 분석','카페·디저트의 개업 후 2년 생존율과 개·폐업 흐름을 살펴봅니다.',horizontal=True)
    st.radio('창업자용 기능',['카페·디저트 분석','자리 이력 찾기'],horizontal=True,key='founder_mode')
    if st.session_state.founder_mode=='자리 이력 찾기':
        spot_history()
        data_status()
        return
    st.markdown('<div class="dfb-quick-note">현재 실제 데이터가 제공된 업종은 카페·디저트뿐입니다. 임대료·유동인구·매출은 포함되지 않으며, 과거 기록으로 개별 가게의 성공을 예측하지 않습니다.</div>',unsafe_allow_html=True)
    filters('founder')
    left,right=st.columns([1.78,.94],gap='large')
    with left:map_area('founder')
    with right:founder_panel()
    data_status()


def report_payload(rec):
    base=REPORT_EXAMPLES.get(rec['unit'],{})
    status={'active_food_stores':int(rec['n_active']),'store_change_3y':float(rec['growth_past3']),
            'openings_3y_per_store':float(rec['open_rate']),
            'closures_3y_per_store':float(rec['close_rate']),
            'population_change_3y':float(rec['pop3']) if pd.notna(rec['pop3']) else None}
    return {
        'unit':rec['unit'],'gu':rec['gu'],'dong':rec['dong'],'as_of':'2025년 말',
        'model_version':rec['model_version'],
        'diagnosis':{'bottleneck':rec['bottleneck'],'confidence':rec['confidence'],
                     'past_accuracy':float(rec['val_accuracy']),'rule_agree':bool(rec['rule_agree']),
                     'entry_rank_pct':float(rec['entry_pct']),'survival_rank_pct':float(rec['surv_pct']),
                     'compared_with':'대구 정체 동 65곳'},
        'top_factors':[x.strip() for x in str(rec['reasons']).split(',') if x.strip()],
        'status':status,
        'policy_types':base.get('policy_types',[]),
        'check_on_site':base.get('check_on_site',[]),
        'support_programs':[],
        'policy_source':('팀 전달 리포트 입력 예시' if base else '연결 전')
    }

def template_report(payload):
    d=payload['diagnosis'];s=payload['status']
    lines=[f"{payload['unit']} · {payload['as_of']}",
        '01 / 진단',
        f"대구 정체 동 65곳 상대 평가: {d['bottleneck']}. 확신도 {d['confidence']}, 과거 동일 구간 적중률 {d['past_accuracy']*100:.0f}%.",
        f"단순 폐업률 규칙과의 방향 {'일치' if d['rule_agree'] else '불일치 — 현장 확인 우선'}.",
        '\n02 / 현황 · 모두 과거 기록',
        f"외식 점포 {s['active_food_stores']:,}곳 / 3년 점포 증감 {s['store_change_3y']*100:+.1f}% / 개업 건수 대 현재 점포 수 {s['openings_3y_per_store']:.3f} / 폐업 건수 대 현재 점포 수 {s['closures_3y_per_store']:.3f} / 주민등록인구 3년 증감 {s['population_change_3y']*100:+.1f}%.",
        '\n03 / 진단에 크게 작용한 변수',
        ' · '.join(payload['top_factors']) or '미제공',
        '\n04 / 먼저 검토할 지원 유형',
        ' · '.join(payload['policy_types']) if payload['policy_types'] else '[연결 예정] 팀 검토 정책 유형 미수신',
        '[연결 예정] 지원사업 DB 연결 후 표시',
        '\n05 / 현장에서 확인할 것',
        ('[필수] 실무 담당자의 현장 조사를 선행해야 합니다. 신규 진입이 적은 이유가 기존 점포의 안정적인 유지인지 수요 부족에 따른 침체인지 이 데이터만으로는 구분할 수 없습니다. 공실·임대료·업종 구성·상권 수요 등을 확인한 뒤 지원 방향을 검토해야 합니다. 지원사업 데이터 유무와 관계없이 현장 조사가 필요합니다.\n' if d['bottleneck']=='진입 병목' else '현장 실사 및 외식 점포 생존 여건 확인을 권고합니다.\n') +
        (' · '.join(payload['check_on_site']) if payload['check_on_site'] else '실제 지역의 이용 수요, 공실, 업종 특성 등을 별도 확인해야 함'),
        '\n06 / 한계',
        '외식 점포 인허가 기록 기반 자료이며 매출을 예측하지 않습니다. 모델은 지원 우선순위를 판단하지 않고, 개별 정책의 효과나 폐업 원인을 입증하지 않습니다.']
    return '\n'.join(lines)

def llm_report(payload):
    """Optional Gemini Free Tier connector. Never sent without a locally configured key.

    NOTE: The developer controls Google project billing. This code cannot prove the
    key is free-tier-only; users must verify quota and disable billing themselves.
    """
    key=os.environ.get('GEMINI_API_KEY')
    if not key:
        try:key=st.secrets.get('GEMINI_API_KEY')
        except Exception:key=None
    if not key:return None
    model='gemini-2.5-flash-lite'  # Free tier at development time; verify again before deployment.
    import requests
    prompt=('아래 전달 데이터에 근거해 한국어 공공기관용 외식 점포 생태계 진단 보고서를 작성하세요. '
         '입력에 없는 수치, 지원사업명, 인과적 원인, 정책 효과를 절대 만들지 마세요. '
         '정체 동 65곳 내 상대 평가임을 명시하고 확신도와 같은 구간의 과거 적중률을 반드시 같이 설명하세요. '
         '과거 적중률은 개별 동 확률이 아닙니다. 지원 우선순위를 정하지 마세요. '
         '지원 유형은 팀 예시 입력에 있을 때만 검토 후보로, 실제 지원사업은 입력이 없으면 미연결로 표시하세요. '
         '모델과 단순 폐업률 규칙이 불일치하면 현장 확인을 강조하세요. '
         '특히 진입 병목은 지나친 안정인지 지역 침체인지 데이터만으로 구별할 수 없으므로, '
         '지원사업 데이터 유무와 관계없이 실무 담당자가 반드시 현장 조사해야 한다고 설명하세요. '
         '매출 예측·개별 점포 성공 예측·인과 해석은 금지합니다. '
         '현황 / 근거 / 검토 가능한 정책 / 현장 조사 / 한계 순서로 작성하세요.\n\n'
         + json.dumps(payload,ensure_ascii=False))
    endpoint=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    response=requests.post(endpoint,headers={'x-goog-api-key':key,'Content-Type':'application/json'},
             json={'contents':[{'role':'user','parts':[{'text':prompt}]}],
                   'generationConfig':{'maxOutputTokens':1700,'temperature':0.15}},timeout=45)
    response.raise_for_status()
    data=response.json()
    text='\n'.join(part.get('text','') for c in data.get('candidates',[])
                   for part in c.get('content',{}).get('parts',[]) if part.get('text'))
    if not text.strip():raise ValueError('Gemini API에서 보고서 텍스트가 반환되지 않았습니다.')
    return text.strip()

def enforce_required_survey(text,payload):
    """Structural safeguard independent of LLM output and policy data presence."""
    if payload['diagnosis']['bottleneck']!='진입 병목':return text
    mandatory=('\n\n[필수 현장 조사] 진입 병목만으로 해당 지역이 기존 음식점의 안정적 유지로 '
               '신규 진입이 적은 상태인지, 수요 부족 등으로 침체되어 신규 진입이 적은 상태인지 '
               '구별할 수 없습니다. 따라서 지원사업 목록 제공 여부와 관계없이 실무 담당자의 '
               '현장 조사를 반드시 선행해야 합니다. 공실, 임대료, 업종 구성, 지역 수요 등을 '
               '확인한 뒤 지원 방향을 검토해야 합니다.')
    if '[필수 현장 조사]' not in text:return text+mandatory
    return text

def report():
    header('report');nav('report')
    page_lead('03','동별 진단 리포트','모델의 판단 근거를 현황·확신도와 구분해 확인합니다.')
    u=st.session_state.selected_unit;rec=O.get(u)
    if not rec or not rec['diagnosis_scope'].startswith('진단'):
        st.info('이 동은 정체 동 병목 진단 대상이 아니어서 병목 리포트를 생성하지 않습니다.')
        if st.button('담당자 지도로 돌아가기'):go('officer')
        return
    payload=report_payload(rec)
    row_right,row_left=st.columns([.75,1.75],gap='large')
    with row_right:
        st.markdown('**REPORT ACTION**')
        st.caption('2025년 말 실제 모델 결과. 무료 요금제 Gemini 키가 없으면 템플릿만 표시합니다. 실제 API는 아직 연결·검증되지 않았습니다.')
        if st.button('LLM 보고서 생성  ↗',type='primary',use_container_width=True,key='btn_llm'):
            with st.spinner('보고서 생성 중...'):
                try:
                    generated=llm_report(payload)
                    if generated:st.session_state.report_output={'type':'LLM','unit':u,'text':enforce_required_survey(generated,payload)}
                    else:st.session_state.report_output={'type':'TEMPLATE','unit':u,'text':enforce_required_survey(template_report(payload),payload)}
                except Exception as err:st.error(f'LLM API 요청 실패: {type(err).__name__} · 연결과 키 설정을 확인해 주세요.')
        if st.session_state.report_output is None or st.session_state.report_output['unit']!=u:
            st.session_state.report_output={'type':'TEMPLATE','unit':u,'text':enforce_required_survey(template_report(payload),payload)}
        is_llm=st.session_state.report_output['type']=='LLM'
        st.markdown('**작성 상태:** '+('Gemini API 실제 호출 결과' if is_llm else '검증 가능한 데이터 기반 템플릿 (LLM 미호출)'))
        if rec['bottleneck']=='진입 병목':
            st.warning('필수 검토: 진입 부족이 안정적인 기존 점포 구조 때문인지 침체 때문인지는 현장 확인 전 단정할 수 없습니다. 실무 담당자의 현장 조사를 반드시 선행해야 합니다.')
        st.caption('지원사업 목록 미수신 · 조원 정책 유형은 예시 입력이 있는 동만 표기')
        st.download_button('리포트 텍스트 저장',data=st.session_state.report_output['text'],file_name=f'daegu_report_{rec["dong"]}.txt',mime='text/plain',use_container_width=True)
        if st.button('← 담당자용 지도로 돌아가기',use_container_width=True):go('officer')
    with row_left:
        st.markdown(f'''<div class="report-frame"><div class="detail-overline">DAEGU FOOD BIZ · V2 REPORT · 2025</div>
         <div class="detail-title" style="font-size:37px">{escape(u)}</div>
         <div class="detail-meta">실제 모델 입력 · 상대적 병목 진단 · 과거 구간 적중률은 개별 지역 확률이 아님</div>
         <div style="margin:16px 0">{box_tag(rec['bottleneck'])}</div>
         <div class="metric-row"><div><span>확신도</span><br><strong>{escape(rec['confidence'])}</strong></div><div><span>과거 동일 구간 적중률</span><br><strong>{float(rec['val_accuracy'])*100:.0f}%</strong></div><div><span>규칙 일치</span><br><strong>{'일치' if rec['rule_agree'] else '불일치 · 현장 확인'}</strong></div></div>
         <div class="report-section"><span class="count">01 / REPORT</span><h3>{'LLM 작성 보고서' if is_llm else '데이터 기반 보고서 미리보기'}</h3><p style="white-space:pre-wrap">{escape(st.session_state.report_output['text'])}</p></div>
         <div class="report-section"><span class="count">02 / POLICY DATA</span><h3>정책과 지원사업</h3><p>{escape(' · '.join(payload['policy_types'])) if payload['policy_types'] else '팀 검토 정책 유형 연결 예정'}</p><p>[연결 예정] 지원사업 DB 연결 후 표시</p></div>
         </div>''',unsafe_allow_html=True)
    data_status()

pages={'home':landing,'officer':officer,'founder':founder,'report':report}
pages.get(st.session_state.view,landing)()
