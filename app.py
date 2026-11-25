"""DAEGU FOOD BIZ · HTML/SVG interface hosted at the existing Streamlit Cloud URL.
The local SVG map handles clicks without rerunning Streamlit; CSV/GeoJSON
inputs refresh when files change. PostgreSQL/LLM are not yet connected.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlsplit, urlunsplit, urlencode
import requests
from html import escape
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
    stop=html.index(';\nconst REPORT_BASE=',start)
    return html[:start]+'const DATA='+encoded+html[stop:]

try:
    html=html_from_sources(file_signature())
except Exception as exc:
    st.error('전달 데이터 또는 화면을 불러오지 못했습니다.')
    st.code(f'{type(exc).__name__}: {exc}')
    st.stop()

# v1.1: Secure report route. Existing HTML/SVG UI remains unchanged.
GEMINI_MODEL = 'gemini-3.5-flash-lite'   # verified free-tier text generation model

def _value(x):
    return None if pd.isna(x) else x.item() if hasattr(x, 'item') else x

def _pct(x, signed=False):
    if x is None or pd.isna(x):
        return '자료 없음'
    n = float(x) * 100
    return f'{n:+.1f}%' if signed else f'{n:.1f}%'

def _key():
    try:
        return str(st.secrets.get('GEMINI_API_KEY', '')).strip()
    except Exception:
        return os.environ.get('GEMINI_API_KEY', '').strip()

def _free_confirmed():
    try:
        value = st.secrets.get('GEMINI_FREE_TIER_CONFIRMED', False)
    except Exception:
        value = os.environ.get('GEMINI_FREE_TIER_CONFIRMED', '')
    return str(value).lower() in ('true', '1', 'yes')

def _input_for_report(unit: str):
    frame=pd.read_csv(ROOT/'data/officer_dongs.csv',encoding='utf-8-sig')
    matches=frame.loc[frame['unit'].eq(unit)]
    if matches.empty:
        return None
    r={k:_value(v) for k,v in matches.iloc[0].items()}
    if not str(r.get('diagnosis_scope', '')).startswith('진단'):
        return {'unit':unit, 'out_of_scope':True}
    examples=json.loads((ROOT/'llm/report_input_example.json').read_text(encoding='utf-8'))
    ex=next((x for x in examples if x.get('unit')==unit), {})
    diagnosis={
        'bottleneck':r['bottleneck'], 'confidence':r['confidence'],
        'past_accuracy':r['val_accuracy'], 'rule_agree':r['rule_agree'],
        'entry_rank_pct':r['entry_pct'], 'survival_rank_pct':r['surv_pct'],
        'compared_with':'대구 정체 동 65곳'
    }
    return {
        'unit':unit,'gu':r['gu'],'dong':r['dong'],'as_of':'2025년 말',
        'model_version':r.get('model_version'),'diagnosis':diagnosis,
        'top_factors':[x.strip() for x in str(r['reasons'] or '').split(',') if x.strip()],
        'status':{
            'active_food_stores':r['n_active'],
            'store_change_3y':r['growth_past3'],
            'openings_3y_per_store':r['open_rate'],
            'closures_3y_per_store':r['close_rate'],
            'population_change_3y':r['pop3'],
        },
        # Only the sample rows supplied by teammates have team-provided policy types.
        'policy_types':ex.get('policy_types', []),
        'check_on_site':ex.get('check_on_site', []),
        'support_programs':[],   # Actual support-program DB has not been received.
    }

def _field_survey(bottleneck: str):
    if bottleneck=='진입 병목':
        return ('[필수] 실무 담당자의 현장 조사를 반드시 선행해야 합니다. 기존 점포가 안정적으로 유지되어 '
                '신규 진입이 적은 경우인지, 상권이 침체되어 신규 진입이 적은 경우인지 모델만으로 구별할 수 없습니다. '
                '공실·임대료·업종 구성·지역 수요를 확인한 뒤 정책 방향을 검토해야 합니다. '
                '지원사업 데이터가 제공되더라도 현장 조사 필요성은 변하지 않습니다.')
    return ('실무 담당자는 임대료, 업종 과밀 여부, 폐업 사유와 현장 수요를 확인하고 '
            '정책의 적합성을 검토해야 합니다. 모델 진단만으로 정책 효과를 단정할 수 없습니다.')

def _grounded_draft(d):
    g=d['diagnosis'];s=d['status'];v=d['top_factors']
    agree='일치' if g['rule_agree'] else '불일치(현장 확인 우선)'
    return '\n'.join([
      '01 / 병목 유형과 확신도',
      f"{d['unit']}은(는) {g['bottleneck']}으로 진단됐습니다. 확신도 {g['confidence']}, 과거 동일 구간 적중률 {_pct(g['past_accuracy'])}. 단순 규칙과의 방향: {agree}.",
      '대구 정체 동 65곳과 비교한 상대 평가이며, 개별 동의 성공 확률이나 정책 지원 우선순위가 아닙니다.',
      '', '02 / 지역 현황',
      f"영업 중 외식 점포 {s['active_food_stores']:,}곳, 최근 3년 점포 증감 {_pct(s['store_change_3y'],True)}, 개업 건수/현재 점포 수 {_pct(s['openings_3y_per_store'])}, 폐업 건수/현재 점포 수 {_pct(s['closures_3y_per_store'])}, 인구 3년 증감 {_pct(s['population_change_3y'],True)}.",
      '', '03 / 진단에 작용한 주요 변수',
      ', '.join(v) if v else '제공된 변수 설명 없음',
      '', '04 / 정책 검토',
      ('팀 제공 검토 유형(지원사업 확정 아님): '+', '.join(d['policy_types'])) if d['policy_types'] else '검토 유형 자료 미제공',
      '[연결 예정] 지원사업 데이터베이스 수신 후 검증된 사업명·자격 요건을 연계합니다.',
      '', '05 / 현장 조사', _field_survey(g['bottleneck']),
      '', '06 / 해석상 한계',
      '외식 점포 인허가 기록과 인구 변수를 이용한 분석입니다. 매출 예측이나 개별 점포 성공 예측, 지원 우선순위 결정에 사용할 수 없습니다. 과거 병목 유형 적중률은 약 70%이며 단순 폐업률 규칙 대비 우월성이 입증된 것은 아닙니다.'
    ])

def _prompt(d):
    rules=(ROOT/'llm/report_rules.md').read_text(encoding='utf-8')
    return ("너는 지방자치단체 담당자를 위해 근거 중심의 외식 점포 생태계 진단 보고서를 작성한다.\n"
            "아래 규칙을 충실히 따르고 약 900~1300자 한국어 보고서를 작성하라. 제공되지 않은 사업명, 원인, 수치를 만들어내지 마라.\n"
            "과거 적중률은 개별 지역의 미래 확률이 아니다. 정책은 가능성·검토 대상으로만 기술한다.\n"
            "모델이 4칸 예측을 하지 않으며 병목 유형 과거 적중률 약 70%는 단순 폐업률 규칙 수준임을 솔직하게 명시한다.\n"
            "특히 진입 병목이라면 안정적 상권인지 침체 지역인지 결정할 수 없으므로, 지원사업 유무와 관계없이 현장 조사가 반드시 필요하다고 명시한다.\n"
            "지원사업 목록은 비어 있으므로 실제 사업명을 작성하지 않는다.\n\n"
            f"팀 보고서 작성 규칙:\n{rules}\n\n검증된 입력 JSON:\n{json.dumps(d,ensure_ascii=False,default=str)}")

@st.cache_data(ttl=6*60*60, max_entries=300, show_spinner=False)
def _gemini_generate_cached(unit: str, data_json: str, _api_key: str):
    # The API key lives server-side in Streamlit Secrets and is never embedded in HTML.
    data=json.loads(data_json)
    response=requests.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent',
        headers={'x-goog-api-key':_api_key, 'Content-Type':'application/json'},
        json={'contents':[{'role':'user','parts':[{'text':_prompt(data)}]}],
              'generationConfig':{'temperature':0.15,'maxOutputTokens':2000}},
        timeout=45,
    )
    if response.status_code==429:
        raise RuntimeError('무료 사용 한도에 도달했습니다. 잠시 후 다시 시도해 주세요. 유료 모델로 전환하지 않습니다.')
    if response.status_code in (401,403):
        raise RuntimeError('Gemini API 키 또는 프로젝트 권한을 확인해 주세요.')
    if response.status_code==404:
        raise RuntimeError('선택한 Gemini 무료 모델을 이 API 키로 사용할 수 없습니다. Google AI Studio의 모델 사용 가능 여부를 확인해 주세요.')
    if not response.ok:
        raise RuntimeError(f'Gemini API 응답 오류 (HTTP {response.status_code}). 잠시 후 다시 시도해 주세요.')
    payload=response.json()
    text='\n'.join(part.get('text','') for c in payload.get('candidates',[]) for part in c.get('content',{}).get('parts',[]))
    if not text.strip():
        raise RuntimeError('Gemini가 텍스트를 반환하지 않았습니다. 검증된 기본 보고서를 사용해 주세요.')
    return text.strip()

def _report_back_url(unit: str) -> str:
    """Return to the officer map and restore the previously viewed region/layer."""
    base_url=urlsplit(st.context.url)
    available_gus=set(pd.read_csv(ROOT/'data/officer_dongs.csv',usecols=['gu'])['gu'].dropna())
    gu=st.query_params.get('return_gu','대구 전체')
    if gu!='대구 전체' and gu not in available_gus:
        gu='대구 전체'
    layer=st.query_params.get('return_layer','diagnosis')
    if layer not in ('diagnosis','status'):
        layer='diagnosis'
    query=urlencode({'map_unit':unit,'map_gu':gu,'map_layer':layer})
    return urlunsplit((base_url.scheme,base_url.netloc,base_url.path,query,''))


def _draft_html(base: str) -> str:
    """Render source-only text as a legible report, never as pale code text."""
    chunks=[]
    for line in base.splitlines():
        line=line.strip()
        if not line:
            continue
        safe_line=escape(line)
        if len(line)>4 and line[:2].isdigit() and line[2:5]==' / ':
            chunks.append(f'<h3>{safe_line}</h3>')
        else:
            chunks.append(f'<p>{safe_line}</p>')
    return '<section class="dfb-report-paper">'+''.join(chunks)+'</section>'


def show_report_page(unit: str):
    d=_input_for_report(unit)
    if d is None:
        st.error('선택한 지역의 데이터가 없습니다.')
        return
    if d.get('out_of_scope'):
        st.warning('이 지역은 병목 예측 대상이 아닙니다. 담당자용 지도에서 과거 현황만 확인할 수 있습니다.')
        return

    # These styles apply only to the native report route; the HTML map/landing
    # page, animations and filters are not altered.
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"],.block-container{
      max-width:1020px!important;margin:0 auto!important;padding:32px 28px 48px!important;
    }
    .dfb-report-title{font-weight:850;font-size:42px;letter-spacing:-.065em;margin:12px 0 8px;color:#111214!important}
    .dfb-rule{border-top:1px solid #242424;margin-bottom:24px}
    .dfb-kicker{font-size:11px;letter-spacing:.17em;color:#6b717a!important;font-weight:750}
    .dfb-report-paper{
      background:#fff;border:1px solid #d9dce0;padding:27px 30px 31px;
      color:#17191c!important;font-size:14px;line-height:1.8;
    }
    .dfb-report-paper h3{font-size:17px!important;font-weight:800!important;color:#111214!important;
       margin:23px 0 8px!important;letter-spacing:-.03em}
    .dfb-report-paper h3:first-child{margin-top:0!important}
    .dfb-report-paper p{font-size:14px!important;line-height:1.8!important;
       color:#17191c!important;margin:0 0 9px!important;opacity:1!important}
    .dfb-report-subtitle{font-size:14px;color:#15171b!important;font-weight:800;
        letter-spacing:-.02em;padding:9px 0 13px}
    [data-testid="stButton"] button,
    [data-testid="stDownloadButton"] button {
       background:#17181b!important;border:1px solid #17181b!important;
       color:#fff!important;-webkit-text-fill-color:#fff!important;
       border-radius:0!important;min-height:45px!important;
       font-size:12px!important;font-weight:750!important;
       width:100%!important;padding:8px 10px!important;
    }
    [data-testid="stButton"] button p,
    [data-testid="stDownloadButton"] button p,
    [data-testid="stButton"] button span,
    [data-testid="stDownloadButton"] button span{
       color:#fff!important;-webkit-text-fill-color:#fff!important;
       white-space:nowrap!important;
    }
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stButton"] button[data-testid="stBaseButton-primary"]{
       background:#B52E43!important;border-color:#B52E43!important;
    }
    [data-testid="stButton"] button:hover,
    [data-testid="stDownloadButton"] button:hover{
       background:#34373b!important;border-color:#34373b!important;
    }
    [data-testid="stButton"] button[kind="primary"]:hover,
    [data-testid="stButton"] button[data-testid="stBaseButton-primary"]:hover{background:#96283A!important;border-color:#96283A!important}
    .dfb-back-link{box-sizing:border-box;display:flex;justify-content:center;
       align-items:center;text-align:center;text-decoration:none!important;
       background:#17181b!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
       border:1px solid #17181b;min-height:45px;width:100%;font-size:12px;
       font-weight:750;padding:8px 10px;white-space:nowrap}
    .dfb-back-link:hover{background:#34373b!important;color:#fff!important}
    @media print{
      [data-testid="stButton"],[data-testid="stDownloadButton"],.dfb-back-link{display:none!important}
      .dfb-report-paper{border:0!important;padding:0!important}
    }
    </style>""",unsafe_allow_html=True)
    st.markdown('<div class="dfb-rule"></div><div class="dfb-kicker">DAEGU FOOD BIZ · DISTRICT REPORT</div><div class="dfb-report-title">동별 진단 리포트</div>',unsafe_allow_html=True)
    st.caption(f"{unit} · 2025년 말 · 검증된 외식 점포 분석 자료")
    st.markdown('**병목 유형:** '+str(d['diagnosis']['bottleneck'])+'　|　**확신도:** '+str(d['diagnosis']['confidence']))
    st.caption('대구 정체 동 65곳과의 상대 평가 · 과거 적중률은 지역별 성공 확률이 아닙니다.')
    base=_grounded_draft(d)
    generated=st.session_state.get('dfb_generated',{}).get(unit)
    report_modes=st.session_state.setdefault('dfb_report_modes',{})
    mode=report_modes.get(unit,'ai' if generated else 'draft')
    if mode=='ai' and not generated:
        mode='draft'
        report_modes[unit]='draft'

    st.markdown('### 근거 자료 기반 보고서')
    if mode=='ai' and generated:
        st.markdown('<div class="dfb-report-subtitle">Gemini AI 작성 보고서</div>',unsafe_allow_html=True)
        # Native markdown for LLM-generated headings/lists, with explicit high
        # contrast styles defined above. Never send this text as pale st.text().
        with st.container(border=True):
            st.markdown(generated)
    else:
        st.markdown('<div class="dfb-report-subtitle">검증된 데이터 기반 기본 초안</div>',unsafe_allow_html=True)
        st.markdown(_draft_html(base),unsafe_allow_html=True)

    # Must remain outside the AI-generated document so the LLM cannot omit it.
    if d['diagnosis']['bottleneck']=='진입 병목':
        st.warning('**필수 현장 조사** — '+_field_survey('진입 병목'))

    st.markdown('---')
    key=_key()
    confirmed=_free_confirmed()
    ready=bool(key and confirmed)
    has_ai=bool(generated)
    # All controls are kept on one row with the same monochrome UI language;
    # only the AI action uses an accent color. No captions under buttons.
    c1,c2,c3,c4=st.columns([1.0,1.75,1.3,1.42],gap='small')
    with c1:
        if st.button('초안 보기',key=f'draft_{unit}',use_container_width=True):
            report_modes[unit]='draft'
            st.rerun()
    with c2:
        ai_label='AI 보고서 보기' if has_ai and mode=='draft' else ('Gemini 무료 AI 보고서 생성' if not has_ai else 'AI 보고서 다시 생성')
        if st.button(ai_label,type='primary',key=f'gemini_{unit}',disabled=not (ready or (has_ai and mode=='draft')),use_container_width=True):
            if has_ai and mode=='draft':
                report_modes[unit]='ai'
                st.rerun()
            else:
                with st.spinner('공개 분석 자료로 보고서를 작성하는 중입니다...'):
                    try:
                        result=_gemini_generate_cached(unit,json.dumps(d,ensure_ascii=False,sort_keys=True,default=str),key)
                        st.session_state.setdefault('dfb_generated',{})[unit]=result
                        report_modes[unit]='ai'
                        st.rerun()
                    except (RuntimeError,requests.RequestException) as exc:
                        st.error(str(exc))
    with c3:
        text_to_save=(generated if mode=='ai' and generated else base)
        if d['diagnosis']['bottleneck']=='진입 병목':
            text_to_save+='\n\n필수 현장 조사: '+_field_survey('진입 병목')
        st.download_button('보고서 다운로드',data=text_to_save,
            file_name=f'daegu_food_biz_{unit.replace(" ","_")}_report.txt',
            mime='text/plain;charset=utf-8',use_container_width=True)
    with c4:
        back_url=escape(_report_back_url(unit),quote=True)
        st.markdown(f'<a class="dfb-back-link" href="{back_url}" target="_self">← 지도로 돌아가기</a>',unsafe_allow_html=True)

    if not key:
        st.info('무료 Gemini API 키가 아직 등록되지 않았습니다. Streamlit Secrets에 GEMINI_API_KEY를 등록하면 AI 보고서를 생성할 수 있습니다.')
    elif not confirmed:
        st.warning('무료 프로젝트·결제 미연결 여부를 확인한 후 GEMINI_FREE_TIER_CONFIRMED = true를 설정해 주세요.')

# Handle native report page in a new tab. This keeps the existing map mounted.
requested_unit=st.query_params.get('report_unit')
if requested_unit:
    show_report_page(str(requested_unit))
    st.stop()

# Streamlit>=1.67 auto-sizes the iframe to its HTML content.
# Browser-side map clicks update panels without rerunning/remounting the map.
# Use the actual Cloud URL; the link opens a native server-side report page.
parts=urlsplit(st.context.url)
report_base=urlunsplit((parts.scheme,parts.netloc,parts.path,'',''))
html=html.replace('const REPORT_BASE="";', 'const REPORT_BASE='+json.dumps(report_base,ensure_ascii=False).replace('<','\u003c')+';',1)
# Initial map state is restored only for the native report back-link.
requested_map_unit=st.query_params.get('map_unit')
if requested_map_unit:
    officer_df=pd.read_csv(ROOT/'data/officer_dongs.csv',usecols=['unit','gu'])
    match=officer_df.loc[officer_df['unit'].eq(requested_map_unit)]
    if not match.empty:
        requested_gu=st.query_params.get('map_gu','대구 전체')
        valid_gus=set(officer_df['gu'].dropna())
        if requested_gu!='대구 전체' and requested_gu not in valid_gus:
            requested_gu='대구 전체'
        if requested_gu!='대구 전체' and requested_gu!=match.iloc[0]['gu']:
            requested_gu='대구 전체'
        requested_layer=st.query_params.get('map_layer','diagnosis')
        if requested_layer not in ('diagnosis','status'):
            requested_layer='diagnosis'
        values=[json.dumps(x,ensure_ascii=False).replace('<','\\u003c') for x in (requested_map_unit,requested_gu,requested_layer)]
        init=('stats.page="officer";stats.unit='+values[0]+';stats.gu='+values[1]
              +';stats.layer='+values[2]+';stats.firstHome=false;')
        html=html.replace('function pageGo(p){',init+'\nfunction pageGo(p){',1)

st.iframe(html,width='stretch',height='content',alt='대구 외식 상권 내비게이터: 동별 병목 진단 및 창업자 분석')
