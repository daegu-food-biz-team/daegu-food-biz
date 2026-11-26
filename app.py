"""DAEGU FOOD BIZ · HTML/SVG interface hosted at the existing Streamlit Cloud URL.
The local SVG map handles clicks without rerunning Streamlit; CSV/GeoJSON
inputs refresh when files change. Gemini reports use Streamlit Secrets.
"""
from __future__ import annotations
import json
import os
import re
import time
import random
from urllib.parse import urlsplit, urlunsplit, urlencode
import requests
from html import escape
from pathlib import Path
import pandas as pd
import streamlit as st
from data_access import read_files, load_geometry, map_features, bound_extent
from report_pdf import make_report_pdf

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
    paths=[ROOT/'data/officer_dongs.csv',ROOT/'data/founder_cafe.csv',ROOT/'data/unit_hjd_map.csv',ROOT/'geo/daegu_hjd_ver20261001.geojson',ROOT/'geo/daegu_boundary_web.geojson',ROOT/'llm/report_input_example.json',ROOT/'preview_quick_open.html']
    return tuple((str(p.relative_to(ROOT)),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)

def _update_legend_in_streamlit_html(html: str) -> str:
    """Apply the compact officer map legend while leaving all other UI intact.

    This runs on the existing HTML template loaded by the Streamlit app, so only
    app.py needs to be uploaded to GitHub. Founder legend and map/LLM handlers
    are unchanged.
    """
    markers = (
        '  return `<section class="legend-compact" aria-label="동별 병목 지도 색상 범례">',
        '  return `<section class="legend-compact" aria-label="동별 병목 진단 지도 색상 범례">',
    )
    start = next((html.find(x) for x in markers if html.find(x) >= 0), -1)
    if start < 0:
        return html  # Keep the app operable if an unrelated template is deployed.
    end_marker = '  </section>`;'
    end_start = html.find(end_marker, start)
    if end_start < 0:
        return html
    end = end_start + len(end_marker)
    new_legend = r'''  return `<section class="legend-compact" aria-label="동별 병목 지도 색상 범례">
    <div class="legend-heading"><strong>색상 기준</strong></div>
    <div class="dfb-legend-top-row">
      <div class="dfb-legend-entry-line legend-palette"><span class="palette-label palette-entry">진입 병목</span>${['높음','보통','낮음'].map(c=>`<span><i class="swatch" style="background:${confColors['진입 병목'][c]}"></i>${c}</span>`).join('')}</div>
      <div class="dfb-legend-gray-line">
        <strong>회색 지역</strong>
        <span><i class="swatch" style="background:#C4CDD8"></i>정체 동 아님 / 자료 미제공</span>
        <span><i class="swatch" style="background:#A7B0BB"></i>읍·면 (병목 진단 범위 밖)</span>
      </div>
    </div>
    <div class="dfb-legend-survival-line legend-palette"><span class="palette-label palette-survival">생존 병목</span>${['높음','보통','낮음'].map(c=>`<span><i class="swatch" style="background:${confColors['생존 병목'][c]}"></i>${c}</span>`).join('')}</div>
    <div class="legend-description-group">
      <div class="legend-description-line"><strong>진입 병목</strong><span>기존 점포 생존에 비해 신규 진입이 상대적으로 적은 유형</span></div>
      <div class="legend-description-line"><strong>생존 병목</strong><span>신규 진입에 비해 점포 생존 안정성이 상대적으로 취약한 유형</span></div>
    </div>
    <div class="legend-confidence"><strong>색 진하기</strong> · 모델 확신도(과거 적중률 기준), 개별 동의 성공 확률은 아닙니다.</div>
  </section>`;'''
    html = html[:start] + new_legend + html[end:]
    css = r'''
<style id="dfb-officer-legend-singlefile">
  /* Horizontal grey legend, next to the entry bottleneck; no redundant labels. */
  .dfb-legend-top-row{display:flex;align-items:center;gap:clamp(20px,2vw,34px);flex-wrap:nowrap;margin:0 0 11px}
  .dfb-legend-entry-line{display:flex!important;flex:0 0 auto!important;align-items:center!important;gap:10px 13px!important;flex-wrap:nowrap!important}
  .dfb-legend-entry-line>span{white-space:nowrap!important}
  .dfb-legend-gray-line{display:flex;align-items:center;flex:0 0 auto;gap:12px;white-space:nowrap;font-size:11px!important;color:#4a515a;font-weight:650;line-height:1.5}
  .dfb-legend-gray-line strong{border-left:3px solid #929bab;padding-left:9px;white-space:nowrap;color:#222832;font-size:12px!important;font-weight:850!important}
  .dfb-legend-gray-line>span{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
  .dfb-legend-gray-line .swatch{margin-right:0!important;flex:none}
  .dfb-legend-survival-line{display:flex!important;align-items:center!important;gap:10px 13px!important;flex-wrap:nowrap!important}
  .dfb-legend-survival-line>span{white-space:nowrap!important}
  .legend-compact .dfb-legend-top-row + .dfb-legend-survival-line{margin-top:0!important}
  @media(max-width:1200px){
    .dfb-legend-top-row{flex-wrap:wrap;gap:10px 24px}
    .dfb-legend-gray-line{padding-left:105px;max-width:100%;overflow-x:auto;scrollbar-width:thin}
  }
  @media(max-width:640px){
    .dfb-legend-gray-line{padding-left:0;gap:8px;max-width:100%}
    .dfb-legend-entry-line,.dfb-legend-survival-line{flex-wrap:wrap!important}
  }
</style>'''
    return html.replace('</head>', css + '</head>', 1)


def _fix_missing_map_regions(html: str) -> str:
    # Render legal-dong polygons even when analysis data is absent.
    replacements = [
        (
            "let opts=units.filter(u=>stats.gu==='대구 전체'||off[u].gu===stats.gu);",
            "let opts=[...new Set(DATA.geo.features.map(ft=>ft.properties.UNIT).filter(Boolean))].filter(u=>stats.gu==='대구 전체'||u.startsWith(stats.gu+' ')).sort((a,b)=>a.localeCompare(b,'ko'));",
        ),
        (
            "function officerPanel(){const r=off[stats.unit],is=r.diagnosis_scope.startsWith('진단');",
            "function officerPanel(){const r=off[stats.unit];if(!r)return missingUnitPanel(stats.unit);const is=r.diagnosis_scope.startsWith('진단');",
        ),
        (
            "function cafePanel(){const r=founders[stats.unit];if(!r)return '<div class=\"note\">자료 미제공</div>';",
            "function cafePanel(){const r=founders[stats.unit];if(!r)return missingUnitPanel(stats.unit);",
        ),
        (
            "function chooseUnit(u){\n if(!off[u])return;",
            "function chooseUnit(u){\n if(!u)return;",
        ),
        (
            "if(p&&p.UNIT&&off[p.UNIT]){chooseUnit(p.UNIT);}",
            "if(p&&p.UNIT){chooseUnit(p.UNIT);}",
        ),
    ]
    for old, new in replacements:
        if html.count(old)!=1:
            raise ValueError('지도 연결 패치 대상이 예상과 다릅니다: '+old[:70])
        html=html.replace(old,new,1)
    extra = '''function missingUnitPanel(u){
 const pos=u.indexOf(' '),gu=pos>=0?u.slice(0,pos):'',dong=pos>=0?u.slice(pos+1):u;
 return `<div class="map-title">지역 분석</div><div class="detail-panel"><div class="detail-overline">${safe(gu)}</div><div class="detail-title">${safe(dong)}</div><div class="warning" style="margin-top:18px">분석 자료 없음</div><div class="body-note" style="margin-top:10px;line-height:1.7">지도 경계는 제공되지만 이 지역은 현재 외식 점포 분석 CSV에 포함되지 않았습니다. 병목 진단·점포 현황을 표시하지 않습니다.</div></div>`;
}
'''
    anchor='function officerPanel(){'
    if html.count(anchor)!=1:
        raise ValueError('지역 분석 패널을 찾지 못했습니다.')
    return html.replace(anchor,extra+anchor,1)

def _add_status_missing_data_legend(html: str) -> str:
    """Show the actual missing-analysis polygon color in the status-map legend.

    This is a presentation-only modification to the HTML rendered inside the
    existing Streamlit app. The other maps, data, and reporting are unchanged.
    """
    # The template's status branch renders five growth-rate bins. Add only the
    # missing-analysis key (used when there is a polygon but no officer CSV row).
    key = "if(stats.layer==='status')return `<section"
    begin = html.find(key)
    if begin < 0:
        raise ValueError('점포 증감률 지도 범례를 찾을 수 없습니다.')
    end = html.find('  </section>`;', begin)
    if end < 0:
        raise ValueError('점포 증감률 지도 범례 끝을 찾을 수 없습니다.')
    legend = html[begin:end]
    tag = '</div>'
    # Last closing div before section end closes the existing legend-palette.
    place = legend.rfind(tag)
    if place < 0 or 'legend-palette' not in legend:
        raise ValueError('점포 증감률 색인 구조가 예상과 다릅니다.')
    add = ('\n    <div class="legend-meta-row" style="margin-top:9px">'
           '<span><i class="swatch" style="background:#C4CDD8"></i>'
           '<strong>분석 미제공</strong></span></div>')
    if '분석 미제공</strong>' in legend:
        return html  # idempotent
    return html[:begin + place + len(tag)] + add + html[begin + place + len(tag):]


@st.cache_data(show_spinner=False)
def html_from_sources(signature):
    html=(ROOT/'preview_quick_open.html').read_text(encoding='utf-8')
    html=_fix_missing_map_regions(_update_legend_in_streamlit_html(html))
    html=_add_status_missing_data_legend(html)
    # Founder-only: separate 'no data' grey from the 63–69% survival band.
    # Update both the actual polygon fill and its legend swatch.
    html=html.replace(
        "if(role==='founder'){if(!f)return '#E4E8EC';",
        "if(role==='founder'){if(!f)return '#A7B0BC';", 1)
    html=html.replace(
        'style="background:#E4E8EC"></i><strong>회색</strong> · 자료 없음',
        'style="background:#A7B0BC"></i><strong>회색</strong> · 자료 없음', 1)
    officer,founder,mapping=read_files()
    geometry,mode=load_geometry()
    geo,stats=map_features(officer,founder,mapping,geometry,mode)
    # Preserve the real legal-dong unit even for 68 locations without analysis
    # results. This is display metadata only; no predictions are fabricated.
    if mode=='legal':
        for mapped_ft, raw_ft in zip(geo['features'],geometry['features']):
            raw_unit=str((raw_ft.get('properties') or {}).get('unit') or '').strip()
            if raw_unit and not mapped_ft['properties'].get('UNIT'):
                mapped_ft['properties']['UNIT']=raw_unit
                mapped_ft['properties']['PHYSICAL_NAME']=raw_unit
                mapped_ft['properties']['NO_OFFICER_DATA']=True
    def rows(df):
        return [{k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in d.items()} for d in df.to_dict('records')]
    payload={'officer':rows(officer),'founder':rows(founder),'geo':geo,'bounds':bound_extent(geo),'stats':stats,'examples':json.loads((ROOT/'llm/report_input_example.json').read_text('utf-8')),'geomMode':mode}
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e')
    start=html.index('const DATA=')
    stop=html.index(';\nconst REPORT_BASE=',start)
    return html[:start]+'const DATA='+encoded+html[stop:]

# Defer loading the heavy SVG map/HTML until a map route is requested.
# New-tab reports should not rebuild the map before showing their own content.

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
                '실제 지원 방향은 현장 상황을 확인한 뒤 신중하게 검토해야 합니다.')
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
      ('검토 가능한 지원 유형: '+', '.join(d['policy_types'])) if d['policy_types'] else '지원 방향은 현장 상황 확인 후 검토',
      '현장 조사 결과를 바탕으로 지원 방향의 적합성을 검토합니다.',
      '', '05 / 현장 조사', _field_survey(g['bottleneck']),
      '', '06 / 해석상 한계',
      '외식 점포 인허가 기록과 인구 변수를 이용한 분석입니다. 매출 예측이나 개별 점포 성공 예측, 지원 우선순위 결정에 사용할 수 없습니다. 과거 병목 유형 적중률은 약 70%이며 단순 폐업률 규칙 대비 우월성이 입증된 것은 아닙니다.'
    ])

def _prompt(d):
    """Ask for an evidence-linked *specific* report, without unverified policies."""
    rules=(ROOT/'llm/report_rules.md').read_text(encoding='utf-8')
    rules='\n'.join(line for line in rules.splitlines() if not re.search(r'DB|데이터베이스|지원사업 데이터|연결 사업', line, re.I))
    # Send explicit display units so the LLM does not mistake ratios for store counts.
    metrics=[{'지표':name,'검증값':value,'설명':note}
             for name,value,note in _report_metric_cells(d)]
    return (
        "너는 대구광역시 외식 상권 담당자의 의사결정을 돕는 데이터 분석가다. "
        "기존 보고서처럼 형식만 갖춘 짧은 요약은 불합격이다. 지역의 검증된 숫자와 요인을 반드시 연결하여, "
        "현장 조사 설계까지 가능한 구체적인 실무 분석을 작성하라. "
        "하지만 입력에 없는 지역 특성이나 인과관계를 추측해 사실처럼 쓰는 것도 불합격이다.\n\n"
        "[반환 형식] 한국어 자연어로 된 JSON 객체 1개만 반환. 마크다운·HTML·코드블록·글머리표·외부 설명 금지. "
        "키 이름은 그대로 유지하고, 아래 문자열/배열을 모두 포함한다.\n"
        '{"summary":"핵심 진단 3~4문장",'
        '"interpretation":"숫자와 원인을 연결한 해석 4~6문장",'
        '"factors":["요인별 근거와 의미를 담은 구체적 문장 1","문장 2","문장 3"],'
        '"support_directions":["확인 조건·근거·검토 목적이 있는 조건부 방향"],'
        '"onsite_checks":["확인 질문 + 확인 방법/자료 + 판별 목적"],'
        '"decision_paths":["현장에서 A가 확인되면 → 다음에 검토할 사항", "B가 확인되면 → 다른 검토 사항"],'
        '"limitations":"해석상 한계 2~3문장"}\n\n'
        "[지역별 구체성: 필수 품질 기준]\n"
        "1) summary(약 140~230자): 대상 동, 병목 유형, 비교 기준(대구 정체 동 65곳), "
        "검증된 현황 수치 2개 이상을 포함해 *이 지역에서 무엇이 동시에 나타났는지* 설명한다. "
        "확신도가 과거 동일 구간 적중률임을 구분하고 미래 확률처럼 해석하지 않는다.\n"
        "2) interpretation(약 250~430자): 최근 3년 점포 증감률, 개업/폐업 건수 대비 비율, 인구 변화 가운데 "
        "입력에 있는 2~4개를 연결한다. 예를 들어 점포 감소와 개·폐업 비율의 관계 또는 인구와 점포 흐름의 방향이 "
        "같은지 다른지를 숫자로 비교한다. 이것은 과거 관측 결과이며 매출·원인을 직접 측정한 값이 아니다. "
        "'따라서 ~일 가능성을 점검해야 한다'처럼 근거→해석→남은 불확실성 순서로 쓴다. "
        "top_factors와 상반되는 징후가 있으면 감추지 말고 밝힌다.\n"
        "3) factors: 실제 top_factors의 각 항목을 가능한 한 하나씩 짚어 3개 문장(각 약 80~140자)을 쓴다. "
        "각 문장은 '관측된 요인 → 진단과 연결되는 이유 → 아직 확인 안 된 변수' 순서로 작성한다. "
        "같은 뜻의 표현 반복, 공허한 '지원이 필요하다' 문장 금지.\n"
        "4) support_directions: 정책 시행을 지시하지 말고 검토할 지원 *유형*만 제안한다. "
        "policy_types가 있다면 그 목록의 표현만 사용하여 각 1~2문장(각 90~160자)으로 "
        "'이 지역의 근거 → 왜 검토 후보인지 → 무엇이 확인되어야 검토할 수 있는지'를 설명한다. "
        "policy_types가 없다면 구체적인 시행 사업명이나 지원 대상 자격을 만들어내지 말고, "
        "병목 진단과 실제 확인된 지표에 근거해 현장 조사를 먼저 수행한 후 검토할 실무 방향 2~3개를 제시한다. "
        "각 방향은 '관찰된 근거 → 현장 확인 조건 → 조건이 맞을 때 검토할 조치' 순서로 쓴다. "
        "데이터베이스 구축 계획, 연결 예정, 미표시 안내는 본문에 쓰지 않는다. "
        "support_programs가 비어 있으면 절대로 실제 사업명, 시행기관, 선정 조건, 예산액, 지원 금액, 성과를 만들지 않는다. "
        "최종 지원 우선순위는 정하지 않는다.\n"
        "5) onsite_checks: 현장 담당자가 바로 사용할 질문 3~4개(각 70~135자). "
        "각 항목은 (가) 어떤 사실을 확인할지 (나) 무엇을 수집·관찰할지 "
        "(다) 어떤 해석을 구분하는 데 쓰일지를 명확히 포함한다."
        " 진입 병목이라면 *안정적 기존 점포 때문에 신규 진입이 낮은 경우*와 *수요 저하/진입 장애로 신규 진입이 낮은 경우*를 "
        "현장 조사로 구분하는 과정을 반드시 포함한다. 생존 병목은 개업 후 초기 이탈 여부, "
        "폐업 사유, 업종 구성 및 비용 조건의 확인을 우선 제안하되 관측하지 않은 사실을 단언하지 않는다.\n"
        "6) decision_paths: 현장 확인 결과에 따라 다음 검토가 달라지는 조건부 문장 2개(각 80~145자). "
        "예: '실제 공실과 신규 진입 장애가 확인된다면 → 원인별 현장 지원 검토', "
        "'공실이 적고 기존 점포가 안정적이면 → 무리한 신규 유치 대신 추가 수요 조사'. "
        "이 예는 가상 조건이지 해당 지역의 확인된 사실이 아니다. 병목 유형에 맞게 새로 쓰되 "
        "지원 효과를 단정하거나 존재하지 않는 지원사업명을 쓰지 않는다.\n"
        "7) limitations(2~3문장): 인허가·인구 기반 상대 진단이며 매출·개별 점포 성공·정책 효과를 예측하지 않는다고 명시. "
        "과거 병목 유형 적중률은 단순 폐업률 규칙 대비 우월성을 보장하지 않는다.\n"
        "8) 본문 합계는 약 1,500~2,300자. 분량만 늘리지 말고 문장마다 지역의 근거, 검증 단계, 혹은 판단상의 의미를 넣는다. "
        "'상권 활성화 필요', '지원이 시급하다', '매출 증가 기대', '정책 시행을 권고한다' 등 단정적 표현 금지. "
        "rule_agree=false면 단순 지표와 모델 결과가 엇갈린다는 점과 현장 확인 우선 원칙을 분명히 쓴다.\n\n"
        "[수치 표기 규칙] 아래 '검증값'을 *그대로* 인용하라. 원시 JSON의 개업/폐업 비율(예: 1.718)은 "
        "1.72건/점포 같은 비율이지 1.72개 점포나 172% 폐업률이 아니다. "
        "원본에 없는 외부 평균·지역 순위·공실률·관광객·임대료 수준·고객 수·매출 등은 숫자든 사실이든 추가 금지. "
        "top_factors의 '높음/낮음'은 입력에 제공된 상대적 분류이며 해당 값의 수치를 임의로 계산하지 마라.\n"
        f"검증된 화면 지표: {json.dumps(metrics,ensure_ascii=False)}\n\n"
        f"팀 보고서 운영 규칙(상충 시 사실과 안전 관련 규칙을 우선):\n{rules}\n\n"
        f"지역별 입력 데이터(JSON):\n{json.dumps(d,ensure_ascii=False,default=str)}"
    )



def _clean_report_language(value):
    """Avoid stale statements about databases that the project does not use."""
    s=str(value or '')
    replacements={
        '현장 조사 후 실제 지원사업 DB와 대조하여 검토합니다. 사업명·지원 자격은 아직 표시하지 않습니다.':
            '현장 조사 결과를 바탕으로 지원 방향을 검토합니다.',
        '사업명과 지원 대상은 검증된 지원사업 DB 연계 후 확인해야 합니다.':
            '지원 방향은 지역 현황과 현장 조사 결과를 함께 검토해 판단합니다.',
        '[연결 예정] 지원사업 데이터베이스 수신 후 검증된 사업명·자격 요건을 연계합니다.':
            '현장 조사 결과를 바탕으로 적용 가능한 지원 방향을 검토합니다.',
        '검증된 지원 유형 자료가 없어 현장 확인 후 지원사업 DB 대조가 필요합니다':
            '지역의 실제 여건을 먼저 확인한 뒤 적절한 지원 방향을 검토합니다',
        '[연결 예정] 지원사업 DB 연결 후 표시':
            '현장 여건을 확인한 후 지원 방향 검토',
    }
    for before,after in replacements.items():
        s=s.replace(before,after)
    return s

def _ai_report_payload(raw: str):
    """Parse Gemini JSON, including recoverable partial/truncated responses."""
    value=str(raw or '').strip()
    value=re.sub(r'^```(?:json)?\s*|\s*```$', '', value, flags=re.I).strip()
    try:
        obj=json.loads(value)
    except (ValueError,TypeError):
        first=value.find('{')
        last=value.rfind('}')
        try:
            obj=json.loads(value[first:last+1]) if first>=0 and last>first else None
        except (ValueError,TypeError):
            obj=None
    keys=('summary','interpretation','limitations','factors','support_directions','onsite_checks','decision_paths')
    if not isinstance(obj,dict):
        # Recover complete property values even when the outer JSON was
        # interrupted by a response token limit. Never output the raw blob.
        obj={}
        decoder=json.JSONDecoder()
        for key in keys:
            match=re.search(r'"'+re.escape(key)+r'"\s*:', value)
            if not match:
                continue
            fragment=value[match.end():].lstrip()
            try:
                parsed,_=decoder.raw_decode(fragment)
            except ValueError:
                parsed=None
            if parsed is not None:
                obj[key]=parsed
                continue
            if fragment.startswith('"'):
                # Recover a completed quoted string if possible.
                for stop in range(2,len(fragment)+1):
                    if fragment[stop-1]!='"':
                        continue
                    try:
                        recovered=json.loads(fragment[:stop])
                        obj[key]=recovered
                        break
                    except ValueError:
                        pass
            elif fragment.startswith('['):
                # Recover complete string elements from a truncated list.
                next_field=re.search(r',\s*"(?:'+ '|'.join(keys) + r')"\s*:', fragment)
                sliced=fragment[:next_field.start()] if next_field else fragment
                entries=[]
                for quoted in re.finditer(r'"(?:\\.|[^"\\])*"',sliced):
                    try:
                        entries.append(json.loads(quoted.group()))
                    except ValueError:
                        pass
                if entries:
                    obj[key]=entries
    if not isinstance(obj,dict) or not isinstance(obj.get('summary'),str) or not obj['summary'].strip():
        return None
    for key in ('summary','interpretation','limitations'):
        item=obj.get(key,'')
        obj[key]=_clean_report_language(item.strip()[:1400]) if isinstance(item,str) else ''
    for key in ('factors','support_directions','onsite_checks','decision_paths'):
        item=obj.get(key,[])
        if isinstance(item,str):
            item=[item]
        if not isinstance(item,list):
            item=[]
        obj[key]=[_clean_report_language(x.strip()[:650]) for x in item if isinstance(x,str) and x.strip()][:5]
    return obj

def _report_metric_cells(d):
    """Measured numbers come only from CSV, never generated LLM text."""
    stt=d['status']
    active=stt.get('active_food_stores')
    active_label=f'{int(active):,}곳' if active is not None else '자료 없음'
    def ratio(x):
        return '자료 없음' if x is None else f'{float(x):.2f}건/점포'
    return [
        ('영업 중 외식 점포',active_label,'2025년 말'),
        ('최근 3년 점포 증감',_pct(stt.get('store_change_3y'),True),'과거 현황'),
        ('최근 3년 개업',ratio(stt.get('openings_3y_per_store')),'현재 점포 수 대비'),
        ('최근 3년 폐업',ratio(stt.get('closures_3y_per_store')),'현재 점포 수 대비'),
        ('최근 3년 인구 변화',_pct(stt.get('population_change_3y'),True),'주민등록 기준'),
    ]


def _ai_report_html(raw: str, d) -> str:
    """Consistent accessible report design, even if the model omits formatting."""
    obj=_ai_report_payload(raw)
    def e(v):
        return escape(str(v or ''),quote=True)
    def bullets(values):
        if not values:
            return '<p class="dfb-ai-muted">제공된 자료로 확인할 내용이 없습니다.</p>'
        return '<ul class="dfb-ai-list">'+''.join(f'<li>{e(x)}</li>' for x in values)+'</ul>'
    def section(number,title,body,extra=''):
        return (f'<section class="dfb-ai-section {extra}">'
                f'<div class="dfb-ai-sec-head"><span>{number}</span><h3>{e(title)}</h3></div>'
                f'<div class="dfb-ai-sec-body">{body}</div></section>')
    metrics=''.join('<div class="dfb-ai-metric"><div class="dfb-ai-metric-label">'+e(label)+'</div>'
                    '<div class="dfb-ai-metric-value">'+e(value)+'</div>'
                    '<div class="dfb-ai-metric-note">'+e(note)+'</div></div>'
                    for label,value,note in _report_metric_cells(d))
    if obj is not None:
        intro=(f'<div class="dfb-ai-summary-tag">핵심 요약</div>'
               f'<p class="dfb-ai-summary-text">{e(obj["summary"])}</p>'
               + (f'<p class="dfb-ai-summary-sub">{e(obj["interpretation"])}</p>' if obj['interpretation'] else ''))
        content=(section('01','근거 숫자','<div class="dfb-ai-metrics">'+metrics+'</div>')
                 + section('02','진단에 작용한 요인',bullets(obj['factors']))
                 + '<div class="dfb-ai-side-grid">'
                 +section('03','먼저 검토할 지원 방향',bullets(obj['support_directions']),'dfb-ai-side')
                 +section('04','현장에서 확인할 사항',bullets(obj['onsite_checks']),'dfb-ai-side')
                 +'</div>'
                 +(section('05','현장 결과에 따른 다음 판단',
                    '<div class="dfb-ai-decisions">'+''.join(
                        f'<div class="dfb-ai-decision"><span class="dfb-ai-decision-index">조건 {i}</span><p>{e(x)}</p></div>'
                        for i,x in enumerate(obj['decision_paths'],1))+'</div>') if obj['decision_paths'] else '')
                 +section('06' if obj['decision_paths'] else '05','분석의 한계',f'<p>{e(obj["limitations"])}</p>','dfb-ai-limits'))
    else:
        # Failed structured output should become a readable, verified draft,
        # not a wall of raw JSON; genuine older plain text remains supported.
        looks_like_json=bool(re.search(r'^\s*(?:```json\s*)?[\{\[]',str(raw or ''),re.I))
        if looks_like_json:
            return ('<div class="dfb-ai-muted" style="margin-bottom:12px">'
                    'AI 응답 일부가 손상되어 검증된 기본 초안을 대신 표시합니다. '
                    'AI 보고서를 다시 생성하면 새 구조로 확인할 수 있습니다.</div>'
                    + _draft_report_html(d))
        lines=_clean_report_language(str(raw or '')).splitlines()
        parts=[]; buf=[]
        def flush():
            if buf:
                parts.append('<p>'+e(' '.join(buf))+'</p>')
                buf.clear()
        for line in lines:
            clean=line.strip()
            if not clean:
                flush();continue
            if re.match(r'^#{1,5}\s+|^\d+[.)]\s+[^:]+$',clean):
                flush()
                title=re.sub(r'^#{1,5}\s+|^\d+[.)]\s*','',clean)
                parts.append('<h4>'+e(title)+'</h4>')
            elif re.match(r'^[-*•]\s+',clean):
                flush();parts.append('<div class="dfb-ai-legacy-bullet">'+e(re.sub(r'^[-*•]\s+','',clean))+'</div>')
            else:
                buf.append(clean)
        flush()
        intro=('<div class="dfb-ai-summary-tag">AI 분석</div>'
               '<p class="dfb-ai-summary-text">기존 생성 보고서를 표시하고 있습니다. '
               '새 구성으로 다시 생성하면 요약·요인·지원 방향이 구분되어 나타납니다.</p>')
        content=(section('01','근거 숫자','<div class="dfb-ai-metrics">'+metrics+'</div>')
                 +section('02','AI 분석 내용',''.join(parts),'dfb-ai-legacy'))
    return '<article class="dfb-ai-report"><div class="dfb-ai-summary">'+intro+'</div>'+content+'</article>'


def _ai_report_pdf_text(raw: str, d) -> str:
    """Make structured results human-readable for the existing Korean PDF writer."""
    obj=_ai_report_payload(raw)
    if obj is None:
        if re.search(r'^\s*(?:```json\s*)?[\{\[]',str(raw or ''),re.I):
            return _grounded_draft(d)
        return _clean_report_language(str(raw))
    parts=['01 / 핵심 요약',obj['summary'],obj['interpretation'],'',
           '02 / 검증된 근거 숫자']
    parts.extend(f'- {name}: {value} ({note})' for name,value,note in _report_metric_cells(d))
    parts.extend(['','03 / 진단에 작용한 요인'])
    parts.extend('- '+x for x in obj['factors'])
    parts.extend(['','04 / 먼저 검토할 지원 방향'])
    parts.extend('- '+x for x in obj['support_directions'])
    parts.extend(['','05 / 현장 확인 사항'])
    parts.extend('- '+x for x in obj['onsite_checks'])
    if obj['decision_paths']:
        parts.extend(['','06 / 현장 결과에 따른 다음 판단'])
        parts.extend(f'- 조건 {i}: {x}' for i,x in enumerate(obj['decision_paths'],1))
    parts.extend(['','07 / 해석상의 한계' if obj['decision_paths'] else '06 / 해석상의 한계',obj['limitations']])
    return '\n'.join(parts)

@st.cache_data(ttl=6*60*60, max_entries=300, show_spinner=False)
def _gemini_generate_cached(unit: str, data_json: str, _api_key: str):
    """Generate AI report with bounded retries for transient Gemini server failures.

    Never retry 429 quota errors or authentication errors; never expose the API key.
    A failed request is not cached, so the existing draft remains available.
    """
    data = json.loads(data_json)
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
    headers = {'x-goog-api-key': _api_key, 'Content-Type': 'application/json'}
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': _prompt(data)}]}],
        'generationConfig': {
            'temperature': 0.15,
            'maxOutputTokens': 6200,
            'responseMimeType': 'application/json',
        },
    }
    transient_codes = {500, 502, 503, 504}
    max_attempts = 3  # first request + at most 2 retries

    for attempt in range(max_attempts):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == max_attempts - 1:
                raise RuntimeError(
                    'Gemini 서버 연결이 불안정해 자동 재시도 후에도 응답을 받지 못했습니다. '
                    '기본 초안은 계속 사용할 수 있습니다.'
                ) from exc
        else:
            if response.ok:
                try:
                    body = response.json()
                except ValueError as exc:
                    raise RuntimeError('Gemini 응답 형식을 읽을 수 없습니다. 기본 초안을 사용해 주세요.') from exc
                result = '\n'.join(
                    part.get('text', '')
                    for candidate in body.get('candidates', [])
                    for part in candidate.get('content', {}).get('parts', [])
                    if isinstance(part, dict)
                )
                if not result.strip():
                    raise RuntimeError('Gemini가 보고서 내용을 반환하지 않았습니다. 기본 초안을 사용해 주세요.')
                return result.strip()
            if response.status_code == 429:
                raise RuntimeError('Gemini API 사용량 한도(HTTP 429)를 확인해 주세요. 자동 재시도하지 않습니다.')
            if response.status_code in (401, 403):
                raise RuntimeError('Gemini API 키 또는 프로젝트 권한을 확인해 주세요.')
            if response.status_code == 404:
                raise RuntimeError('선택한 Gemini 모델을 사용할 수 없습니다. Google AI Studio에서 모델 사용 가능 여부를 확인해 주세요.')
            if response.status_code not in transient_codes:
                raise RuntimeError(f'Gemini API 응답 오류 (HTTP {response.status_code}).')
            if attempt == max_attempts - 1:
                raise RuntimeError(
                    f'Gemini 서버가 일시적으로 응답하지 않습니다 (HTTP {response.status_code}). '
                    '자동 재시도 2회 후에도 실패했습니다. 기본 초안은 계속 사용할 수 있습니다.'
                )
        # Exponential backoff with jitter to avoid retry storms (no extra quota requests on 429).
        time.sleep((2 ** attempt) + random.uniform(0.0, 0.4))

    raise RuntimeError('Gemini 보고서를 생성하지 못했습니다. 기본 초안을 이용해 주세요.')

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



def _draft_report_html(d) -> str:
    """Render the source-only first draft in the same visual system as AI reports.

    All observations and factors come from officer CSV / supplied report examples;
    no missing policy names or model outcomes are invented for the draft.
    """
    def e(value):
        return escape(str(value if value is not None else '자료 없음'), quote=True)

    g=d['diagnosis']
    s=d['status']
    kind=str(g['bottleneck'])
    if kind=='진입 병목':
        meaning='기존 점포의 생존에 비해 신규 진입이 상대적으로 적은 유형입니다.'
    else:
        meaning='신규 진입에 비해 점포 생존 안정성이 상대적으로 취약한 유형입니다.'
    accuracy=_pct(g.get('past_accuracy'))
    consistency='일치' if g.get('rule_agree') else '불일치 · 현장 확인 우선'

    def section(index, title, contents, extra=''):
        return (f'<section class="dfb-ai-section {extra}">'
                f'<div class="dfb-ai-sec-head"><span>{index}</span><h3>{e(title)}</h3></div>'
                f'<div class="dfb-ai-sec-body">{contents}</div></section>')

    def lines(items):
        if not items:
            return '<p class="dfb-ai-muted">제공된 분석 자료가 없습니다.</p>'
        return '<ul class="dfb-ai-list">'+''.join(f'<li>{e(x)}</li>' for x in items)+'</ul>'

    overview=(f'<div class="dfb-ai-summary-tag">진단 요약 · 2025년 말</div>'
              f'<p class="dfb-ai-summary-text">{e(d["unit"])}은(는) '
              f'<strong>{e(kind)}</strong>으로 진단됐습니다. {e(meaning)}</p>'
              f'<p class="dfb-ai-summary-sub">대구 정체 동 65곳과 비교한 상대 평가입니다. '
              f'병목 분류 확신도는 {e(g.get("confidence"))} '
              f'(과거 같은 확신도 구간 적중률 {e(accuracy)})이며, '
              f'단순 지표와 모델 판정은 <strong>{e(consistency)}</strong>입니다. '
              '이 수치는 해당 지역의 미래 발생 확률이 아닙니다.</p>')

    metric_cards=''.join(
        '<div class="dfb-ai-metric">'
        f'<div class="dfb-ai-metric-label">{e(label)}</div>'
        f'<div class="dfb-ai-metric-value">{e(value)}</div>'
        f'<div class="dfb-ai-metric-note">{e(note)}</div></div>'
        for label,value,note in _report_metric_cells(d)
    )

    factors=list(d.get('top_factors') or [])
    factor_html=(lines(factors) +
                 '<p class="dfb-draft-caption">주요 요인은 모델 입력자료의 상대적 특성입니다. '
                 '요인만으로 원인이나 정책 효과를 단정할 수 없습니다.</p>')

    supplied_types=list(d.get('policy_types') or [])
    if supplied_types:
        support=(lines(supplied_types)
                 +'<p class="dfb-draft-caption">검토 가능한 지원 유형이며, 적용 여부는 해당 지역의 현장 여건 확인 후 판단합니다.</p>')
    elif kind=='진입 병목':
        support=('<p>신규 입점이 적은 이유를 먼저 구분해야 합니다. 실제 공실·임대료와 지역 수요를 확인하고, '
                 '진입 장애가 확인되면 입점 여건 개선을 검토합니다. 기존 점포가 안정적이라면 무리한 신규 유치보다 '
                 '수요와 업종 구성을 추가로 살펴봅니다.</p>')
    else:
        support=('<p>폐업이 집중되는 업력과 실제 폐업 사유를 먼저 확인합니다. 초기 영업 단계의 어려움이 확인되면 '
                 '운영 안정·경영 상담의 필요성을 검토하고, 업종 경쟁이나 비용 부담이 주요 요인인지 현장에서 구분합니다.</p>')

    checks=list(d.get('check_on_site') or [])
    if not checks:
        checks=(['실제 공실 및 신규 입점 가능 공간 확인',
                 '임대료·업종 구성과 지역 수요 조사',
                 '낮은 신규 진입이 안정적인 상권 때문인지 진입 장애 때문인지 구분']
                if kind=='진입 병목'
                else ['초기 영업 점포의 폐업 사유 확인',
                      '업종 집중·경쟁 및 임대료 등 비용 조건 확인',
                      '주민·방문객 수요와 현장 이용 흐름 확인'])
    check_html=lines(checks)

    limitation=('인허가 기록 및 인구 관련 변수에 기반한 과거 자료의 상대적 진단입니다. '
                '매출, 개별 점포 성공, 정책 효과 또는 지원 우선순위를 예측하지 않습니다. '
                '과거 병목 분류 적중률은 단순 폐업률 규칙보다 우수함을 보장하지 않습니다.')
    return (
        '<article class="dfb-ai-report dfb-draft-report">'
        f'<div class="dfb-ai-summary">{overview}</div>'
        + section('01','지역 현황', '<div class="dfb-ai-metrics">'+metric_cards+'</div>')
        + section('02','진단에 작용한 주요 요인',factor_html)
        + '<div class="dfb-ai-side-grid">'
        + section('03','정책 검토',support,'dfb-ai-side')
        + section('04','현장 조사',check_html,'dfb-ai-side')
        + '</div>'
        + section('05','해석상 한계',f'<p>{e(limitation)}</p>','dfb-ai-limits')
        + '</article>'
    )


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
      max-width:980px!important;margin:0 auto!important;padding:22px 26px 26px!important;
    }
    .dfb-report-rule{border-top:2px solid #202125;margin:0 0 16px}
    .dfb-report-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}
    .dfb-report-kicker{font-size:11px;font-weight:800;letter-spacing:.13em;color:#5f6670!important}
    .dfb-report-date{font-size:12px;color:#636a75!important;font-weight:600}
    .dfb-report-title{font-size:clamp(30px,3vw,38px)!important;line-height:1.2!important;font-weight:850!important;
      letter-spacing:-.055em!important;margin:10px 0 8px!important;color:#111214!important}
    .dfb-report-status-badge{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;border-radius:12px;
      background:#f3f0ee;color:#454b55!important;font-size:13px!important;font-weight:800!important;white-space:nowrap}
    .dfb-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:14px 0 18px}
    .dfb-summary-card{border:1px solid #e1e4e8;background:#f7f5f3;padding:18px 18px 16px;border-radius:18px}
    .dfb-summary-card.entry{background:#eef4ff;border-color:#d7e2f6}
    .dfb-summary-card.survival{background:#fff1e6;border-color:#efd4bf}
    .dfb-summary-label{font-size:13px!important;font-weight:800!important;color:#5f6670!important;margin-bottom:8px}
    .dfb-summary-value{font-size:20px!important;line-height:1.3!important;font-weight:850!important;color:#111214!important;letter-spacing:-.03em}
    .dfb-summary-note{font-size:13px!important;color:#555d67!important;line-height:1.55!important;margin-top:6px}
    .dfb-report-brief{border-top:1px solid #e1e4e8;border-bottom:1px solid #e1e4e8;
      padding:10px 0;margin:0 0 14px;font-size:12px!important;line-height:1.65!important;color:#626b76!important}
    .dfb-report-brief strong{color:#242830!important;font-weight:800!important}
    .dfb-report-brief .sep{margin:0 10px;color:#c4c8cf!important}
    @media(max-width:760px){.dfb-summary-grid{grid-template-columns:1fr}.dfb-report-title{font-size:30px!important}.dfb-report-brief .sep{display:none}
      .dfb-report-brief strong{display:inline-block;margin-right:6px}}

    .dfb-report-paper{
      background:#fff;border:1px solid #d9dce0;padding:22px 24px 23px;
      color:#17191c!important;font-size:14px;line-height:1.8;
    }
    .dfb-report-paper h3{font-size:17px!important;font-weight:800!important;color:#111214!important;
       margin:23px 0 8px!important;letter-spacing:-.03em}
    .dfb-report-paper h3:first-child{margin-top:0!important}
    .dfb-report-paper p{font-size:14px!important;line-height:1.8!important;
       color:#17191c!important;margin:0 0 9px!important;opacity:1!important}
    .dfb-report-section-title{display:block;
       font-size:19px!important;line-height:1.5!important;
       font-weight:850!important;letter-spacing:-.025em;margin:20px 0 10px!important;
       padding:0!important;color:#17191c!important}
    .dfb-report-mode{font-size:13px!important;color:#666f79!important;
       font-weight:650!important;letter-spacing:-.01em}
    /* Prevent native Streamlit blocks from inserting oversized gaps between
       the report title, its body, and the action row. */
    [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{
       gap:.5rem!important}
    .dfb-report-paper{margin-top:0!important}
    /* Structured Gemini report: neutral municipal tone, distinct sections, responsive. */
    .dfb-ai-report{font-family:inherit;color:#17202b!important;background:#fff;border:1px solid #e0e3e6;
      border-radius:13px;overflow:hidden;margin:0 0 8px}
    .dfb-draft-report .dfb-ai-summary{background:linear-gradient(105deg,#f5f7fa,#fff 85%);
      border-left-color:#6d819e}
    .dfb-draft-report .dfb-ai-summary-tag{color:#4e647e!important}
    .dfb-draft-report .dfb-ai-summary-text strong{color:#213c63!important}
    .dfb-draft-caption{color:#6a7480!important;font-size:12px!important;
      line-height:1.65!important;margin:12px 0 0!important}
    .dfb-draft-empty{color:#404b5b!important;font-size:14px!important;font-weight:800!important;
      margin:0 0 8px!important}
    .dfb-ai-summary{padding:24px 27px 22px;background:linear-gradient(105deg,#fbf8f5,#fff 80%);
      border-bottom:1px solid #e6e1da;border-left:4px solid #b95b1d}
    .dfb-ai-summary-tag{font-size:12px!important;font-weight:850;color:#9a4f1e!important;letter-spacing:.02em;margin-bottom:10px}
    .dfb-ai-summary-text{font-size:18px!important;line-height:1.75!important;font-weight:760!important;
      letter-spacing:-.02em;color:#1b2635!important;margin:0!important;word-break:keep-all;overflow-wrap:break-word}
    .dfb-ai-summary-sub{font-size:14px!important;line-height:1.8!important;color:#5e6570!important;
      margin:11px 0 0!important;word-break:keep-all;overflow-wrap:break-word}
    .dfb-ai-section{padding:20px 27px 21px;border-bottom:1px solid #e8ebef}
    .dfb-ai-section:last-child{border-bottom:0}
    .dfb-ai-sec-head{display:flex;align-items:baseline;gap:10px;margin:0 0 13px}
    .dfb-ai-sec-head>span{color:#af602a!important;font-size:12px!important;font-weight:850!important;letter-spacing:.05em}
    .dfb-ai-sec-head h3{font-size:16px!important;line-height:1.5!important;font-weight:850!important;
      letter-spacing:-.025em;color:#202630!important;margin:0!important}
    .dfb-ai-sec-body p{font-size:14px!important;line-height:1.75!important;margin:0 0 10px!important;color:#384251!important}
    .dfb-ai-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
    .dfb-ai-metric{border:1px solid #e5e7ea;background:#fafafa;border-radius:9px;padding:14px 15px;min-width:0}
    .dfb-ai-metric-label{font-size:12px!important;color:#66707b!important;font-weight:700!important;margin-bottom:7px}
    .dfb-ai-metric-value{font-size:21px!important;line-height:1.2!important;color:#17202b!important;font-weight:900!important;
      letter-spacing:-.04em;white-space:nowrap}
    .dfb-ai-metric-note{font-size:11px!important;color:#727a85!important;margin-top:8px;line-height:1.4!important}
    .dfb-ai-list{list-style:none!important;padding:0!important;margin:0!important;display:flex;flex-direction:column;gap:12px}
    .dfb-ai-list li{position:relative;padding-left:16px;font-size:14px!important;line-height:1.75!important;
      color:#384251!important;word-break:keep-all;overflow-wrap:break-word}
    .dfb-ai-list li::before{content:' ';position:absolute;top:.7em;left:0;width:6px;height:6px;
      background:#b96129;border-radius:50%}
    .dfb-ai-side-grid{display:grid;grid-template-columns:1fr 1fr;gap:0;border-bottom:1px solid #e8ebef}
    .dfb-ai-side-grid>.dfb-ai-section{border-bottom:0}
    .dfb-ai-side-grid>.dfb-ai-section+.dfb-ai-section{border-left:1px solid #e8ebef}
    .dfb-ai-decisions{display:grid;grid-template-columns:1fr;gap:9px}
    .dfb-ai-decision{display:flex;align-items:flex-start;gap:13px;border:1px solid #e7e8e9;
      background:#fbfbfa;border-radius:10px;padding:12px 15px}
    .dfb-ai-decision-index{flex:none;display:inline-block;padding:5px 7px;border-radius:5px;
      background:#f1ebe4;color:#92501d!important;font-size:11px!important;font-weight:800!important;white-space:nowrap}
    .dfb-ai-decision p{margin:0!important;font-size:14px!important;line-height:1.7!important;color:#384251!important;
      word-break:keep-all;overflow-wrap:break-word}
    .dfb-ai-limits{background:#f8f9fa}
    .dfb-ai-limits .dfb-ai-sec-head>span{color:#7a8795!important}
    .dfb-ai-muted{color:#858c94!important}
    .dfb-ai-legacy h4{font-size:15px!important;margin:13px 0 9px!important;color:#212a37!important}
    .dfb-ai-legacy-bullet{position:relative;padding:3px 0 5px 17px;font-size:14px!important;line-height:1.8!important;color:#384251!important}
    .dfb-ai-legacy-bullet::before{content:'•';position:absolute;left:0;color:#af602a}
    @media(max-width:720px){
      .dfb-ai-summary{padding:19px}.dfb-ai-section{padding:18px}
      .dfb-ai-summary-text{font-size:16px!important}
      .dfb-ai-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
      .dfb-ai-metric-value{font-size:18px!important}
      .dfb-ai-side-grid{grid-template-columns:1fr}
      .dfb-ai-side-grid>.dfb-ai-section+.dfb-ai-section{border-left:0;border-top:1px solid #e8ebef}
    }

    .dfb-close-tab{box-sizing:border-box;display:flex;justify-content:center;align-items:center;
       width:100%;min-height:45px;white-space:nowrap;background:#17181b!important;
       color:#fff!important;-webkit-text-fill-color:#fff!important;
       border:1px solid #17181b;border-radius:0;font-size:12px;font-weight:750;
       cursor:pointer;padding:8px 10px;font-family:inherit}
    .dfb-close-tab:hover{background:#34373b!important;border-color:#34373b!important}
    .dfb-close-fallback{color:#575e66!important;font-size:12px;line-height:1.5;margin-top:7px}
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
    # Compact information hierarchy: location > diagnosis > methodology > report body.
    safe_unit=escape(unit)
    safe_type=escape(str(d['diagnosis']['bottleneck']))
    safe_conf=escape(str(d['diagnosis']['confidence']))
    style='survival' if d['diagnosis']['bottleneck']=='생존 병목' else 'entry'
    simple_compare = '일치' if d['diagnosis'].get('rule_agree') else '추가 확인 필요'
    simple_note = '단순 폐업률 기준 판정과 같은 방향' if d['diagnosis'].get('rule_agree') else '단순 폐업률 기준과 달라 현장 확인 필요'
    accuracy_note = f"과거 같은 구간 적중률 {int(round(float(d['diagnosis']['past_accuracy'])*100))}%"
    status_note = '들어오는 힘보다 버티는 힘이 약함' if d['diagnosis']['bottleneck']=='생존 병목' else '기존 점포 생존에 비해 신규 진입이 적음'
    generated=st.session_state.get('dfb_generated',{}).get(unit)
    report_modes=st.session_state.setdefault('dfb_report_modes',{})
    mode=report_modes.get(unit,'ai' if generated else 'draft')
    if mode=='ai' and not generated:
        mode='draft'
        report_modes[unit]='draft'
    report_kind = 'AI 생성' if mode=='ai' and generated else '기본 초안'
    st.markdown(
        '<div class="dfb-report-rule"></div>'
        '<div class="dfb-report-top"><div><span class="dfb-report-kicker">DAEGU FOOD BIZ · 동별 진단 리포트</span>'
        f'<div class="dfb-report-title">{safe_unit}</div></div>'
        f'<span class="dfb-report-status-badge">{report_kind} · 검토 필요</span></div>'
        '<div class="dfb-report-brief"><strong>분석 기준</strong> 2025년 말'
        '<span class="sep">|</span><strong>비교 대상</strong> 대구 정체 동 65곳'
        '<span class="sep">|</span><strong>해석 기준</strong> 상대적 병목 진단 · 개별 점포 성공 확률 아님</div>'
        '<div class="dfb-summary-grid">'
        f'<div class="dfb-summary-card {style}"><div class="dfb-summary-label">진단</div><div class="dfb-summary-value">{safe_type}</div><div class="dfb-summary-note">{status_note}</div></div>'
        f'<div class="dfb-summary-card"><div class="dfb-summary-label">모델 확신도</div><div class="dfb-summary-value">{safe_conf}</div><div class="dfb-summary-note">{accuracy_note}</div></div>'
        f'<div class="dfb-summary-card"><div class="dfb-summary-label">단순 지표와 비교</div><div class="dfb-summary-value">{simple_compare}</div><div class="dfb-summary-note">{simple_note}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    base=_grounded_draft(d)
    st.markdown(f'<div class="dfb-report-section-title">분석 보고서 <span class="dfb-report-mode">({report_kind})</span></div>',unsafe_allow_html=True)
    if mode=='ai' and generated:
        # Render a consistent report design. Escape all model text before adding HTML.
        st.markdown(_ai_report_html(generated,d),unsafe_allow_html=True)
    else:
        st.markdown(_draft_report_html(d),unsafe_allow_html=True)

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
    c1,c2,c3=st.columns([1.0,1.75,1.3],gap='small')
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
        text_to_save=(_ai_report_pdf_text(generated,d) if mode=='ai' and generated else base)
        if d['diagnosis']['bottleneck']=='진입 병목':
            text_to_save+='\n\n필수 현장 조사: '+_field_survey('진입 병목')
        try:
            pdf_data = make_report_pdf(
                unit=unit, report_text=text_to_save, mode=report_kind,
                bottleneck=str(d['diagnosis']['bottleneck']),
                confidence=str(d['diagnosis']['confidence']),
                as_of=str(d['as_of']),
                survey_note=_field_survey(str(d['diagnosis']['bottleneck'])),
            )
            st.download_button('PDF 다운로드', data=pdf_data,
                file_name=f'daegu_food_biz_{unit.replace(" ", "_")}_report.pdf',
                mime='application/pdf', use_container_width=True,
                key=f'pdf_{unit}_{mode}')
        except Exception as exc:
            st.error('PDF 생성에 실패했습니다. 설치된 PDF 라이브러리와 한글 글꼴을 확인해 주세요.')

    if not key:
        st.info('무료 Gemini API 키가 아직 등록되지 않았습니다. Streamlit Secrets에 GEMINI_API_KEY를 등록하면 AI 보고서를 생성할 수 있습니다.')
    elif not confirmed:
        st.warning('무료 프로젝트·결제 미연결 여부를 확인한 후 GEMINI_FREE_TIER_CONFIRMED = true를 설정해 주세요.')

# Handle native report page in a new tab. This keeps the existing map mounted.
requested_unit=st.query_params.get('report_unit')
if requested_unit:
    show_report_page(str(requested_unit))
    st.stop()

try:
    html=html_from_sources(file_signature())
except Exception as exc:
    st.error('전달 데이터 또는 화면을 불러오지 못했습니다.')
    st.code(f'{type(exc).__name__}: {exc}')
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
