#!/usr/bin/env python3
"""Standalone offline design preview (real 144-area handoff; NOT Streamlit/DB/LLM)."""
from __future__ import annotations
import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data_access import read_files,load_geometry,map_features,bound_extent

o,f,m=read_files();g,mode=load_geometry();joined,stats=map_features(o,f,m,g,mode)
OFFICER=o.to_dict('records');FOUNDER=f.to_dict('records')
# JS null, not NaN; avoid injecting any raw HTML into a <script> element.
import pandas as pd
payload={
 'officer':[{k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in row.items()} for row in OFFICER],
 'founder':[{k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in row.items()} for row in FOUNDER],
 'geo':joined,'bounds':bound_extent(joined),'stats':stats,
 'examples':json.loads((ROOT/'llm/report_input_example.json').read_text('utf-8')),
 'geomMode':mode
}
DATA=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e')
HTML=r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DAEGU FOOD BIZ · UI / 실제 데이터 미리보기</title>
<style>
:root{--ink:#111214;--muted:#737983;--line:#dadce0;--paper:#fafafa}
*{box-sizing:border-box}html,body{margin:0;padding:0;background:#fafafa;color:#111214;font-family:Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif}
main{max-width:1570px;padding:18px 54px 50px;margin:auto}button,select,input{font:inherit}button{cursor:pointer;border:1px solid #bdc2c8;background:transparent;color:#15171a;border-radius:0;padding:10px 14px;font-size:12px;font-weight:750}
button:hover{background:#15171a;color:white}button.selected,button.primary{background:#17181b;color:white;border-color:#17181b}button:disabled{opacity:.4;cursor:default}
.site-header{border-top:1px solid #242424;min-height:67px;padding:19px 1px 12px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.brand-kor{font-weight:850;font-size:16px;letter-spacing:-.055em}.brand-divider{height:23px;border-left:1px solid #bebebe;display:inline-block;margin:0 12px;vertical-align:middle}.brand-eng{font-size:8px;line-height:1.2;display:inline-block;color:#5a6169;font-weight:750;letter-spacing:.075em;vertical-align:middle}.header-right{font-size:10px;color:#202124;font-weight:750;letter-spacing:.22em;white-space:nowrap}
.hero{padding:42px 0 42px;max-width:100%}.hero h1{font-weight:800;font-size:clamp(86px,9.5vw,151px);line-height:.86;letter-spacing:-.085em;margin:0;color:#090909}.hero p{font-weight:600;letter-spacing:-.045em;font-size:clamp(14px,1.5vw,20px);line-height:1.8;margin:30px 0 0;max-width:720px}
.roles{display:grid;grid-template-columns:.49fr .51fr .51fr;gap:26px;margin-top:14px}.role{min-height:174px;padding:0 0 0 28px;border-left:1px solid #9ca0a5}.role .eyebrow{color:#777d86;font-size:11px;font-weight:800;letter-spacing:.22em;margin-bottom:10px}.role-head{font-weight:850;font-size:clamp(26px,3.3vw,42px);letter-spacing:-.075em;line-height:1.35;margin:6px 0 12px}.role-desc{font-size:13px;line-height:1.55;min-height:68px;color:#333b45}.role button{width:100%}.small-footer{color:#91949a;font-size:10px;line-height:1.6;margin-top:32px}
.nav{display:flex;align-items:center;justify-content:flex-end;gap:12px;padding:4px 0 0;flex-wrap:wrap}.nav-caption{font-size:11px;letter-spacing:.1em;color:#878e96;font-weight:650}.nav-buttons{display:flex;flex-wrap:nowrap;gap:0}.nav-buttons button{white-space:nowrap}
.page-lead{padding:12px 0 7px}.overline{font-size:11px;color:#777d86;letter-spacing:.17em;font-weight:750}.page-lead h1{font-size:clamp(31px,3.5vw,50px);letter-spacing:-.065em;margin:10px 0 7px}.page-lead p{color:#687078;font-size:13px;line-height:1.7}.page-lead.inline .title-row{display:flex;align-items:baseline;gap:27px}.page-lead.inline .title-row h1{white-space:nowrap;flex:none}.page-lead.inline .title-row p{margin:0;color:#687078;font-size:12px}.controls{display:flex;gap:14px;margin:8px 0 18px;flex-wrap:wrap;align-items:flex-end}.controls .control-label{flex:1 1 180px;min-width:0}.controls .control-label select{width:100%}.data-stamp{font-size:11px;color:#7b828a;margin:3px 0 12px}.control-label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:#777d86;font-weight:650}select,input{border:1px solid #d6d8dc;background:white;color:#141619;border-radius:0;padding:10px 11px;min-width:180px}
.page-grid{display:grid;grid-template-columns:minmax(0,1.72fr) minmax(270px,.9fr);gap:30px}.map-title{font-size:14px;font-weight:800;letter-spacing:-.03em}.map-sub{font-size:11px;color:#8a8f98;line-height:1.5;margin:4px 0 10px}
.map-wrap{background:#ECEFF2;height:530px;position:relative;border:1px solid #ebedf0;overflow:hidden}.map-svg{height:100%;width:100%;touch-action:none;cursor:grab}.map-svg.dragging{cursor:grabbing}.map-svg path{transition:fill .2s,stroke-width .12s;cursor:pointer;outline:0}.map-svg path:hover{stroke:#14171c;stroke-width:2.2}
.map-info{position:absolute;z-index:2;top:11px;right:11px;width:205px;background:rgba(255,255,255,.97);border:1px solid #cbd0d6;padding:13px;box-shadow:0 2px 10px #0000000b;font-size:11px}.map-info strong{font-size:12px}.info-row{display:flex;justify-content:space-between;gap:13px;line-height:1.5;padding:4px 0}.info-row span{color:#737982}.info-row b{text-align:right;overflow-wrap:anywhere}.info-foot{font-size:10px;color:#878e96;margin-top:7px;border-top:1px solid #e8eaed;padding-top:8px;line-height:1.45}.map-tools{position:absolute;top:11px;left:11px;z-index:3;display:flex;flex-direction:column;gap:0;box-shadow:0 2px 10px #00000009}
.map-tools button{background:#fff;color:#16181b;min-width:35px;min-height:34px;padding:6px 9px;font-size:17px;border:1px solid #cbd0d6}
.map-tools button+button{border-top:0}.map-tools button:hover{background:#17181b;color:#fff}
.map-tools .map-reset{font-size:11px;font-weight:750;padding:9px 8px;min-height:34px}.note{font-size:11px;color:#56616c;line-height:1.55;padding:10px 12px;background:#f1f4f8;border-left:2px solid #7898d6;margin:10px 0}.legend{display:flex;flex-wrap:wrap;gap:9px 14px;margin:14px 0;font-size:11px;color:#555b62}.swatch{display:inline-block;width:11px;height:11px;vertical-align:middle;border:1px solid #ebedef;margin-right:5px}.legend-guide{display:grid;grid-template-columns:repeat(2,1fr);gap:10px 18px;border-top:1px solid #e0e3e6;margin:12px 0;padding:15px 0}.legend-guide div{font-size:11px;line-height:1.6;color:#686f77}.legend-guide strong{color:#232529}
.detail-panel{background:#fff;border:1px solid #dedfe1;padding:24px 25px 17px}.detail-overline{font-size:10px;font-weight:800;color:#376eea;letter-spacing:.17em}.detail-title{font-size:31px;font-weight:850;letter-spacing:-.065em;margin:10px 0}.detail-meta{font-size:11px;color:#7a8089}.signal{font-size:11px;font-weight:750;padding:5px 8px;display:inline-block;background:#edf0f3;color:#55606b;margin-top:14px}.signal.entry{background:#e8effb;color:#1f4fb8}.signal.survival{background:#fbebdf;color:#985019}.metric-row{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #dedfe1;padding:13px 0;margin-top:12px}.metric-row span{font-size:11px;color:#666e77}.metric-row strong{font-size:15px}.metric-big{font-size:38px;letter-spacing:-.055em;font-weight:800;margin-top:5px}.section-title{font-weight:800;font-size:13px;margin:19px 0 7px}
.rank-card{margin:18px 0 0;padding:16px 0 2px;border-top:1px solid #dedfe1;}
.rank-card .rank-heading{font-size:13px;font-weight:850;color:#19202a;letter-spacing:-.04em;margin-bottom:15px}
.rank-line{margin:13px 0}.rank-line .rank-label{display:flex;justify-content:space-between;align-items:baseline;font-size:12px;color:#202b3a;margin-bottom:8px}
.rank-line .rank-label strong{font-weight:800;font-size:12px;color:#19202a}
.rank-track{height:8px;background:#eae7e4;border-radius:20px;overflow:hidden}
.rank-fill{height:100%;border-radius:20px}.rank-fill.entry{background:#277A5C}.rank-fill.survival{background:#71AC89}
.rank-card .foot{font-size:10px;color:#7a818a;line-height:1.55;margin:12px 0 4px}.pill{border:1px solid #dce0e5;font-size:11px;padding:5px 8px;display:inline-block;margin:4px 5px 0 0}.action{margin-top:20px;width:100%}.warning{border-left:3px solid #1f4fb8;background:#f3f5fc;padding:11px 13px;margin:14px 0;color:#47546c;font-size:12px;line-height:1.65}.chart{display:flex;gap:7px;align-items:end;height:165px;border-bottom:1px solid #bfc5cb;padding-bottom:8px;overflow:auto}.bar-group{display:flex;gap:2px;min-width:38px;align-items:end;height:150px}.bar{width:17px;max-height:100%;min-height:2px}.year{font-size:9px;color:#818991;text-align:center}.chart-year{display:inline-flex;flex-direction:column}.report{border:1px solid #d5d8dd;background:white;padding:30px;white-space:pre-wrap;font-size:13px;line-height:1.85;margin:20px 0}.report h2{margin-top:0}.body-note{font-size:12px;color:#555d65;line-height:1.7}.report-actions{display:flex;gap:10px;flex-wrap:wrap}.footer-spacer{height:40px}
@keyframes enter{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:translateY(0)}}body.first-entry .hero{animation:enter .65s ease-out both}body.first-entry .roles{animation:enter .65s .25s both}
@media(prefers-reduced-motion:reduce){body.first-entry .hero,body.first-entry .roles{animation:none}}
@media(max-width:850px){main{padding:14px 18px 25px}.page-grid{grid-template-columns:1fr}.hero h1{font-size:clamp(70px,13vw,100px)}.roles{grid-template-columns:1fr 1fr}.roles .dummy{display:none}.role{padding-left:14px}.role-head{font-size:26px}.brand-eng{display:none}.map-wrap{height:440px}}
@media(max-width:540px){.roles{grid-template-columns:1fr}.page-lead.inline .title-row{flex-wrap:wrap;gap:0}.page-lead.inline .title-row p{width:100%}.map-info{width:180px}.nav-buttons button{font-size:10px;padding:8px}.hero{padding:55px 0 25px}.detail-panel{padding:18px}.legend-guide{grid-template-columns:1fr}}
@media print{.site-header,.nav,.history,.report-actions,.warning,.page-lead,.footer-spacer{display:none!important}main{padding:0!important;max-width:none!important}.report{border:0;padding:10px 0;margin:0;white-space:pre-wrap;font-size:11pt;line-height:1.65}body{background:#fff!important}}
</style></head><body><main id="app"></main>
<script>const DATA=__DATA__;
const off=Object.fromEntries(DATA.officer.map(r=>[r.unit,r]));
const founders=Object.fromEntries(DATA.founder.map(r=>[r.unit,r]));
const support=Object.fromEntries(DATA.examples.map(r=>[r.unit,r]));
const units=Object.keys(off).sort((a,b)=>a.localeCompare(b,'ko'));
const gus=['대구 전체',...new Set(DATA.officer.map(x=>x.gu))].sort((a,b)=>a.localeCompare(b,'ko'));
gus.splice(gus.indexOf('대구 전체'),1);gus.unshift('대구 전체');
const confColors={'진입 병목':{'높음':'#1F4FB8','보통':'#7898D6','낮음':'#CDD9F1'},'생존 병목':{'높음':'#C65A11','보통':'#E5A16F','낮음':'#F4D7C1'}};
const survColors=['#AC4C58','#E3A071','#DCE0E3','#88A9CE','#315FA8'];
const b=(x)=>x===null||x===undefined?'—':String(x);
const safe=(x)=>b(x).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const pct=(x,signed=false)=>x===null||x===undefined?'—':`${signed&&x>=0?'+':''}${(100*x).toFixed(1)}%`;
const stats={page:'home',unit:off['중구 동성로2가']?'중구 동성로2가':units[0],gu:'대구 전체',layer:'diagnosis',founderMode:'cafe',zoom:1,panX:0,panY:0,hover:null,firstHome:true};
function pageGo(p){if(stats.page!==p){stats.page=p;if(p==='home')stats.firstHome=true;render();}}
function nav(){return `<div class="nav"><div class="nav-buttons">${[['home','처음으로'],['officer','담당자용'],['founder','창업자용']].map(([p,n])=>`<button class="${stats.page===p||stats.page==='report'&&p==='officer'?'selected':''}" data-page="${p}">${n}</button>`).join('')}</div></div>`}
function header(){const tags={home:'ROLE SELECT',officer:'01 / DISTRICT DIAGNOSIS',founder:'02 / FOUNDER ANALYTICS',report:'03 / DISTRICT REPORT'};return `<div class="site-header"><div><span class="brand-kor">대구 외식 상권 내비게이터</span><i class="brand-divider"></i><span class="brand-eng">DAEGU F&amp;B<br>COMMERCIAL NAVIGATOR</span></div><span class="header-right">${tags[stats.page]}</span></div>`}
function pageLead(index,name,subtitle,inline=false){return `<div class="page-lead ${inline?'inline':''}"><div class="overline">${index} / DAEGU FOOD BIZ</div><div class="title-row"><h1>${name}</h1><p>${subtitle}</p></div></div>`}
function landing(){return `<div class="hero"><h1>DAEGU<br>FOOD BIZ</h1><p>대구 외식 상권의 현황을 진단하고,<br>입지와 생존 전략을 제안하는 데이터 기반 의사결정 플랫폼입니다.</p></div><div class="roles"><div class="dummy"></div><div class="role"><div class="eyebrow">FOR OPERATORS</div><div class="role-head">상권 담당자용</div><div class="role-desc">지역별 상권을 진단하고 정책 방향을 확인하세요.</div><button class="primary" data-page="officer">진단 지도 열기 ↗</button></div><div class="role"><div class="eyebrow">FOR FOUNDERS</div><div class="role-head">예비 창업자용</div><div class="role-desc">관심 업종의 상권을 분석하고, 입지 결정을 지원받으세요.</div><button data-page="founder">업종 분석 열기 ↗</button></div></div><div class="small-footer">DAEGU FOOD BIZ · FOOD SERVICE DISTRICT INTELLIGENCE<br>외식 점포 인허가 기록 기반 분석이며, 개별 점포 성공이나 매출을 예측하지 않습니다.</div>`}
function selectors(includeLayer=false){let opts=units.filter(u=>stats.gu==='대구 전체'||off[u].gu===stats.gu);if(!opts.includes(stats.unit))stats.unit=opts[0];return `<div class="controls">${includeLayer?`<label class="control-label">지도 레이어<select id="layerChoice"><option value="diagnosis" ${stats.layer==='diagnosis'?'selected':''}>병목 유형 · 확신도</option><option value="status" ${stats.layer==='status'?'selected':''}>3년 점포 증감 · 현황(예측 아님)</option></select></label>`:''}<label class="control-label">구·군 선택<select id="guChoice">${gus.map(g=>`<option ${stats.gu===g?'selected':''}>${safe(g)}</option>`).join('')}</select></label><label class="control-label">법정동·읍면 선택<select id="unitChoice">${opts.map(u=>`<option ${stats.unit===u?'selected':''}>${safe(u)}</option>`).join('')}</select></label></div>`}
function color(u,role){const r=off[u],f=founders[u];if(role==='founder'){if(!f)return '#E4E8EC';const s=f.surv2_adj;return survColors[s<.58?0:s<.63?1:s<.69?2:s<.73?3:4]}if(!r)return '#E4E8EC';if(stats.layer==='status'){const n=r.growth_past3;return n<-.1?'#B94C54':n<-.03?'#E3A5A5':n<.03?'#E9ECEF':n<.1?'#A6BEDB':'#3865A9'}if(r.diagnosis_scope.startsWith('현황만 (읍·면'))return '#A7B0BB';if(!r.diagnosis_scope.startsWith('진단'))return '#C4CDD8';return confColors[r.bottleneck][r.confidence]}
function analysis(u,role){const r=off[u],f=founders[u];if(role==='founder')return f?`카페 개업 후 2년 생존율 ${pct(f.surv2_adj)}`:'카페 자료 없음';if(!r)return '분석 미제공';if(stats.layer==='status')return `3년 점포 증감 ${pct(r.growth_past3,true)} · 현황`;return r.diagnosis_scope.startsWith('진단')?`${r.bottleneck} · 확신도 ${r.confidence}`:r.diagnosis_scope.startsWith('현황만 (읍·면')?'진단 범위 밖 · 과거 현황만':'정체 동 아님 · 현황만'}
const geoBounds=DATA.bounds, centerLat=(geoBounds[0][0]+geoBounds[1][0])/2,centerLon=(geoBounds[0][1]+geoBounds[1][1])/2;
const cos=Math.cos(centerLat*Math.PI/180);const W=850,H=595;
const scale=Math.min((W-80)/((geoBounds[1][1]-geoBounds[0][1])*cos),(H-60)/(geoBounds[1][0]-geoBounds[0][0]));
const pr=([lon,lat])=>[(W/2+(lon-centerLon)*cos*scale),(H/2-(lat-centerLat)*scale)];
function shapePath(ft){let polys=ft.geometry.type==='MultiPolygon'?ft.geometry.coordinates:[ft.geometry.coordinates];return polys.map(poly=>poly.map(ring=>ring.map((pair,i)=>(i?'L':'M')+pr(pair).map(v=>v.toFixed(2)).join(',')).join(' ')+' Z').join(' ')).join(' ')}
function featuresForGu(){return DATA.geo.features.map((ft,i)=>({ft,i})).filter(({ft})=>stats.gu==='대구 전체'||(ft.properties.MAP_MODE==='legal'?ft.properties.UNIT.startsWith(stats.gu+' '):ft.properties.PHYSICAL_NAME.includes(' '+stats.gu+' ')));}
function frameFor(items){
 let minx=Infinity,miny=Infinity,maxx=-Infinity,maxy=-Infinity;
 function walk(obj){if(!Array.isArray(obj)||!obj.length)return;if(typeof obj[0]==='number'){
   const [x,y]=pr(obj);minx=Math.min(minx,x);maxx=Math.max(maxx,x);miny=Math.min(miny,y);maxy=Math.max(maxy,y);
 }else obj.forEach(walk);}
 items.forEach(({ft})=>walk(ft.geometry.coordinates));
 if(!Number.isFinite(minx))return {x:0,y:0,w:W,h:H};
 let wantedW=Math.max(1,(maxx-minx)*1.22), wantedH=Math.max(1,(maxy-miny)*1.22);
 let w=Math.max(wantedW,wantedH*W/H),h=w*H/W;
 return {x:(minx+maxx-w)/2,y:(miny+maxy-h)/2,w,h};
}
function groupTransform(){const {x,y,w,h}=stats.frame||{x:0,y:0,w:W,h:H};let cx=x+w/2,cy=y+h/2;
 return `translate(${cx+stats.panX} ${cy+stats.panY}) scale(${stats.zoom}) translate(${-cx} ${-cy})`;}

function mapInfo(p,role){if(!p)return '<strong>지역 정보</strong><div class="info-foot">동 위에 마우스를 올려 주세요.</div>';
 return `<strong>지역 정보</strong><div class="info-row"><span>지역</span><b>${safe(p.UNIT||p.PHYSICAL_NAME)}</b></div><div class="info-row"><span>지역코드</span><b>${safe(p.CODE)}</b></div><div class="info-row"><span>분석</span><b>${safe(analysis(p.UNIT,role))}</b></div><div class="info-foot">${DATA.geomMode==='admin-preview'?'임시 행정동 경계 · 코드는 행정동 코드'+(p.OVERLAP?`<br>다른 법정동 ${p.OVERLAP}곳도 매핑`:''):'법정동 경계'}</div>`}
function legend(role){if(role==='founder')return `<div class="legend">${[['58% 미만',0],['58~63%',1],['63~69%',2],['69~73%',3],['73% 이상',4]].map(([n,i])=>`<span><i class="swatch" style="background:${survColors[i]}"></i>${n}</span>`).join('')}<span>▨ 표본 20개 미만 빗금</span></div><div class="note">현재 카페·디저트만 실제 자료를 받았어요. 과거 기록이며 개별 점포 성공을 예측하지 않습니다.</div>`;
if(stats.layer==='status')return `<div class="legend">${[['−10% 미만','#B94C54'],['−10% ~ −3%','#E3A5A5'],['−3% ~ +3%','#E9ECEF'],['+3% ~ +10%','#A6BEDB'],['+10% 이상','#3865A9']].map(([n,c])=>`<span><i class="swatch" style="background:${c}"></i>${n}</span>`).join('')}</div><div class="note">최근 3년 점포 증감률은 현황(예측 아님)입니다. 지원 우선순위를 모델이 결정하지 않습니다.</div>`;
return `<div class="legend">${['진입 병목','생존 병목'].map(n=>['높음','보통','낮음'].map(c=>`<span><i class="swatch" style="background:${confColors[n][c]}"></i>${n} · ${c}</span>`).join('')).join('')}<span><i class="swatch" style="background:#C4CDD8"></i>정체 동 아님</span><span><i class="swatch" style="background:#A7B0BB"></i>읍·면 · 진단 범위 밖</span></div><div class="legend-guide"><div><strong>진입 병목</strong><br>기존 점포의 생존에 비해 신규 진입이 상대적으로 적은 유형</div><div><strong>생존 병목</strong><br>신규 진입에 비해 생존 안정이 상대적으로 취약한 유형</div><div><strong>확신도 진하기</strong><br>높음 82% · 보통 73% · 낮음 52%는 과거 동일 구간 적중률. 개별 동의 확률이 아님</div><div><strong>연회색 · 정체 동 아님</strong><br>7개 구의 비정체 동, 과거 현황만 표시</div><div><strong>진회색 · 진단 범위 밖</strong><br>달성군·군위군 14개 읍·면: 과거 현황과 카페 통계만 제공, 병목 예측 없음</div></div>`}
function geoMap(role){
 const visible=featuresForGu();
 stats.frame=frameFor(visible);
 const defs=survColors.map((c,i)=>`<pattern id="hatch${i}" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="${c}"/><path d="M0,0L0,7" stroke="#40464e" stroke-width="1.5"/></pattern>`).join('');
 const paths=visible.map(({ft,i})=>{
  const p=ft.properties,u=p.UNIT;const f=founders[u],c=color(u,role),active=stats.unit===u;
  const sample=role==='founder'&&f&&f.small_sample;
  const baseBand=f?(f.surv2_adj<.58?0:f.surv2_adj<.63?1:f.surv2_adj<.69?2:f.surv2_adj<.73?3:4):0;
  return `<path data-geo="${i}" d="${shapePath(ft)}" fill="${sample?`url(#hatch${baseBand})`:c}" fill-opacity=".96" stroke="${active?'#15191d':'#FFFFFF'}" stroke-width="${active?2.4:1.1}" vector-effect="non-scaling-stroke" fill-rule="evenodd"></path>`
 }).join('');
 let selected=visible.find(({ft})=>ft.properties.UNIT===stats.unit)?.ft.properties;
 return `<div class="map-title">DAEGU · ${DATA.geomMode==='legal'?'LEGAL DONG MAP':'ADMIN DONG PREVIEW'}</div><div class="map-sub">실제 지리적 경계 · ${DATA.geomMode==='legal'?'법정동':'법정동 경계 미수령 → 행정동 대표값 임시 색칠'}</div>
 <div class="map-wrap"><div class="map-tools"><button id="mapZoomIn" aria-label="지도 확대" title="확대">+</button><button id="mapZoomOut" aria-label="지도 축소" title="축소">−</button><button class="map-reset" id="mapReset">${stats.gu==='대구 전체'?'대구 전체':safe(stats.gu)} ↺</button></div><div class="map-info" id="mapInfo">${mapInfo(selected,role)}</div>
 <svg class="map-svg" id="mapSvg" viewBox="${stats.frame.x} ${stats.frame.y} ${stats.frame.w} ${stats.frame.h}" aria-label="${safe(stats.gu)} 경계 지도" xmlns="http://www.w3.org/2000/svg"><defs>${defs}</defs><g id="shapeGroup" transform="${groupTransform()}">${paths}</g></svg></div>
 <div class="note">${DATA.geomMode==='legal'?'법정동 경계를 직접 사용합니다.':`행정동 150개 경계 중 ${DATA.stats.collisions}개는 여러 법정동이 공유합니다. 따라서 임시 지도 색상은 대표 법정동 1곳에 해당하며 모든 법정동의 실제 공간 진단이 아닙니다. 144개 지역의 실측 현황과 65개 정체 동의 병목 진단은 오른쪽 패널·선택 목록에서 조회할 수 있습니다.`}</div>${legend(role)}`;
}
function rankCard(r){if(!r.diagnosis_scope.startsWith('진단'))return '';
 let ep=Math.max(0,Math.min(100,100*r.entry_pct)),sp=Math.max(0,Math.min(100,100*r.surv_pct));
 return `<div class="rank-card"><div class="rank-heading">대구 정체 동 65곳 중 상대 순위</div>
 <div class="rank-line"><div class="rank-label"><span>진입 활력</span><strong>상위 ${Math.max(1,Math.round(100-ep))}%</strong></div><div class="rank-track"><div class="rank-fill entry" style="width:${ep.toFixed(1)}%"></div></div></div>
 <div class="rank-line"><div class="rank-label"><span>생존 안정</span><strong>상위 ${Math.max(1,Math.round(100-sp))}%</strong></div><div class="rank-track"><div class="rank-fill survival" style="width:${sp.toFixed(1)}%"></div></div></div>
 <div class="foot">정체 동 65곳의 상대 평가. 개별 동의 성공 확률이나 정책 지원 우선순위가 아닙니다.</div></div>`;
}
function officerPanel(){const r=off[stats.unit],is=r.diagnosis_scope.startsWith('진단');const stat=is?r.bottleneck:(r.diagnosis_scope.startsWith('현황만 (읍·면')?'진단 범위 밖 · 현황만':'정체 동 아님 · 현황만');const sig=stat==='진입 병목'?'entry':stat==='생존 병목'?'survival':'';
return `<div class="map-title">REGION INSIGHT</div><div class="map-sub">선택한 법정동의 실제 분석값</div><div class="detail-panel"><div class="detail-overline">SELECTED LEGAL DONG / 2025</div><div class="detail-title">${safe(r.dong)}</div><div class="detail-meta">대구광역시 ${safe(r.gu)} · ${safe(r.unit)}</div><div class="signal ${sig}">${safe(stat)}</div><div class="metric-row"><div><span>영업 중 외식 점포</span><div class="metric-big">${Number(r.n_active).toLocaleString('ko-KR')}</div></div><div><span>3년 점포 증감 · 현황</span><div class="metric-big" style="font-size:24px">${pct(r.growth_past3,true)}</div></div></div><div class="metric-row"><div><span>개업 건수 / 점포 수</span><br><strong>${pct(r.open_rate)}</strong></div><div><span>폐업 건수 / 점포 수</span><br><strong>${pct(r.close_rate)}</strong></div></div><div class="metric-row"><div><span>인구 3년 증감</span><br><strong>${pct(r.pop3,true)}</strong></div><div><span>기준</span><br><strong>2025년 말</strong></div></div>${rankCard(r)}${is?`<div class="section-title">확신도 ${r.confidence} · 과거 동일 구간 적중률 ${(100*r.val_accuracy).toFixed(0)}%</div><div class="body-note">개별 지역의 예측 확률이나 지원 우선순위 점수가 아닙니다.</div>${!r.rule_agree?'<div class="warning">단순 규칙과 판정 불일치 · 현장 확인 우선</div>':''}<div class="section-title">진단에 작용한 주요 변수</div>${safe(r.reasons).split(',').map(x=>`<span class="pill">${x.trim()}</span>`).join('')}<button class="primary action" data-page="report">이 동의 진단 리포트 보기 ↗</button>`:`<div class="warning">${r.diagnosis_scope.startsWith('현황만 (읍·면')?'달성군·군위군 읍·면은 모델 검증 범위 밖이므로 병목 진단과 확신도 없이 과거 현황만 제공합니다.':'7개 구의 비정체 동으로 병목 예측 없이 과거 현황만 제공합니다.'}</div>`}</div>`}
function cafePanel(){const r=founders[stats.unit];if(!r)return '<div class="note">자료 미제공</div>';
const yrs=Array.from({length:10},(_,i)=>2016+i);const max=Math.max(...yrs.flatMap(y=>[r['open_'+y],r['close_'+y]]),1);
return `<div class="map-title">CAFE · LOCAL PROFILE</div><div class="map-sub">카페·디저트 / 실제 개업 후 2년 생존율</div><div class="detail-panel"><div class="detail-overline">FOUNDER INSIGHT</div><div class="detail-title">${safe(r.dong)}</div><div class="detail-meta">대구광역시 ${safe(r.gu)} · 카페·디저트</div><div class="metric-row"><div><span>개업 후 2년 생존율 · 보정값</span><div class="metric-big" style="color:#1F4FB8">${pct(r.surv2_adj)}</div></div></div><div class="metric-row"><div><span>관찰 표본</span><br><strong>${r.cohort_n}개</strong></div><div><span>2025년 영업 중</span><br><strong>${r.active_2025}개</strong></div></div><div class="metric-row"><div><span>2022년 영업 중</span><br><strong>${r.active_2022}개</strong></div><div><span>대구 참고 평균</span><br><strong>66.4%</strong></div></div>${r.small_sample?'<div class="warning">표본 20건 미만 · 생존율 보정값 해석 주의</div>':''}</div><div class="section-title">ANNUAL MOVEMENT · 2016–2025</div><div class="body-note" style="margin-bottom:8px"><i class="swatch" style="background:#287A58"></i>개업 &nbsp;&nbsp;<i class="swatch" style="background:#B65359"></i>폐업</div><div class="chart">${yrs.map(y=>`<div class="chart-year"><div class="bar-group"><span class="bar" style="background:#287A58;height:${r['open_'+y]/max*140}px" title="${y} 개업 ${r['open_'+y]}건"></span><span class="bar" style="background:#B65359;height:${r['close_'+y]/max*140}px" title="${y} 폐업 ${r['close_'+y]}건"></span></div><div class="year">${y}</div></div>`).join('')}</div><div class="body-note" style="margin-top:15px">임대료·유동인구·매출은 포함되지 않고, 과거 기록이 개별 점포의 성공을 예측하지 않습니다.</div>`}
function pageBody(){if(stats.page==='home')return landing();if(stats.page==='officer'){return `${nav()}${pageLead('01','동별 병목 진단','7개 구 정체 동 65곳의 병목 진단 · 144개 지역의 과거 현황 조회')}${selectors(true)}<div class="page-grid"><div>${geoMap('officer')}</div><div>${officerPanel()}</div></div><div class="body-note">과거 병목 유형 적중률 70%. 단순 폐업률 규칙보다 우월하다는 근거는 없으며 지원 우선순위는 별도 현황을 보고 판단합니다.</div>`}
if(stats.page==='founder'){return `${nav()}${pageLead('02','업종별 동 분석','카페·디저트의 개업 후 2년 생존율과 개·폐업 흐름을 확인하세요.',true)}<div class="controls"><button data-fmode="cafe" class="${stats.founderMode==='cafe'?'selected':''}">카페·디저트 분석</button><button data-fmode="history" class="${stats.founderMode==='history'?'selected':''}">자리 이력 찾기</button></div>${stats.founderMode==='history'?'<div class="warning">자리 이력 조회는 아직 실제 주소별 인허가 데이터가 없어 연결되지 않았습니다. 현재 파일은 동 단위 집계이며 개별 점포·층·호수 이력을 포함하지 않습니다.</div><label class="control-label">주소 입력 (연동 전)<input placeholder="대구광역시 ○○구 ○○로 00" disabled></label>':`${selectors()}<div class="page-grid"><div>${geoMap('founder')}</div><div>${cafePanel()}</div></div>`}`}
if(stats.page==='report'){const r=off[stats.unit];const ex=support[stats.unit];if(!r.diagnosis_scope.startsWith('진단'))return `${nav()}<div class="warning">이 지역은 병목 진단 대상이 아니며 과거 현황만 제공됩니다.</div>`;
const status=`${stats.unit} · 2025년 말\n\n01 / 진단\n${r.bottleneck}, 확신도 ${r.confidence}, 과거 동일 구간 적중률 ${(100*r.val_accuracy).toFixed(0)}%. 대구 정체 동 65곳과 비교한 상대 평가.\n단순 규칙과 ${r.rule_agree?'일치':'불일치 — 현장 확인 우선'}.\n\n02 / 현황\n영업 중 점포 ${r.n_active}곳. 최근 3년 점포 증감 ${pct(r.growth_past3,true)}. 개업 건수/현재 점포 수 ${pct(r.open_rate)}, 폐업 건수/현재 점포 수 ${pct(r.close_rate)}, 인구 증감 ${pct(r.pop3,true)}.\n\n03 / 주요 요인\n${r.reasons}\n\n04 / 먼저 검토할 지원 유형\n${ex&&ex.policy_types.length?ex.policy_types.join(' · '):'[연결 예정] 팀 정책 유형 미수신'}\n[연결 예정] 지원사업 DB 연결 후 표시\n\n05 / 현장 조사\n${r.bottleneck==='진입 병목'?'[필수] 실무 담당자의 현장 조사가 반드시 필요합니다. 신규 진입이 적은 이유가 기존 점포가 안정적으로 유지되기 때문인지, 상권 침체 때문인지 모델만으로 구별할 수 없습니다. 공실·임대료·업종 구성·현장 수요 확인 후 정책을 검토합니다. 지원사업 데이터 유무와 관계없이 현장 조사는 필수입니다.':'현장 점검을 통해 실제 생존 여건과 해당 지역의 업종 특성을 확인해야 합니다.'}\n\n06 / 한계\n인허가 자료 기반 외식 점포 생태계 분석입니다. 매출 예측이 아니며 지원 우선순위, 개별 점포 성공 확률, 정책 효과를 판단하지 않습니다.`;
return `${nav()}${pageLead('03','동별 진단 리포트','입력 자료 밖의 숫자나 사업명은 만들지 않습니다.')}<div class="report"><div class="detail-overline">DAEGU FOOD BIZ · V2 REPORT / 미리보기 (LLM 미호출)</div><h2>${safe(stats.unit)}</h2><p>${safe(status)}</p></div><div class="warning">HTML 미리보기에서는 LLM API·PostgreSQL·실제 지원사업 조회가 동작하지 않습니다. 정식 앱에서 연결할 수 있습니다.</div><div class="report-actions"><button data-page="officer">← 담당자용 지도로</button><button id="reportPrint" onclick="window.print()">보고서 인쇄 / PDF로 저장</button></div>`}return '';}
function render(){document.body.classList.toggle('first-entry',stats.page==='home'&&stats.firstHome);document.getElementById('app').innerHTML=header()+pageBody()+'<div class="footer-spacer"></div>';wire();if(stats.page==='home')stats.firstHome=false;}
function wire(){document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>{stats.hover=null;pageGo(el.dataset.page)}));document.querySelectorAll('[data-fmode]').forEach(el=>el.addEventListener('click',()=>{stats.founderMode=el.dataset.fmode;render()}));
let gu=document.getElementById('guChoice');if(gu)gu.onchange=()=>{stats.gu=gu.value;stats.zoom=1;stats.panX=0;stats.panY=0;render()};let unit=document.getElementById('unitChoice');if(unit)unit.onchange=()=>{stats.unit=unit.value;render()};let layer=document.getElementById('layerChoice');if(layer)layer.onchange=()=>{stats.layer=layer.value;render()};
if(document.getElementById('mapSvg'))wireMap();}
function wireMap(){
 const svg=document.getElementById('mapSvg'),group=document.getElementById('shapeGroup'),panel=document.getElementById('mapInfo');
 const scene=stats.frame,cx=scene.x+scene.w/2,cy=scene.y+scene.h/2;
 let down=false,move=false,prev=null,downPath=null;
 const transform=()=>group.setAttribute('transform',groupTransform());
 const clamp=()=>{const z=stats.zoom;let dx=(z-1)*scene.w/2,dy=(z-1)*scene.h/2;
   stats.panX=Math.max(-dx,Math.min(dx,stats.panX));stats.panY=Math.max(-dy,Math.min(dy,stats.panY));};
 const cursor=ev=>{let pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;return pt.matrixTransform(svg.getScreenCTM().inverse());};
 const zoomAt=(target,x=cx,y=cy)=>{let next=Math.max(1,Math.min(4.5,target)),ratio=next/stats.zoom;
   if(Math.abs(next-stats.zoom)<1e-6)return;
   stats.panX=(x-cx)-ratio*(x-cx-stats.panX);
   stats.panY=(y-cy)-ratio*(y-cy-stats.panY);
   stats.zoom=next;clamp();transform();};
 const findp=ev=>{let path=ev.target.closest('path[data-geo]');return path?DATA.geo.features[Number(path.dataset.geo)].properties:null};
 svg.addEventListener('pointermove',ev=>{if(down){const pos=cursor(ev);
   if(prev){const dx=pos.x-prev.x,dy=pos.y-prev.y;if(Math.abs(dx)+Math.abs(dy)>.01){stats.panX+=dx;stats.panY+=dy;clamp();transform();move=true;}}
   prev=pos;
 }else{let p=findp(ev);if(p)panel.innerHTML=mapInfo(p,stats.page==='founder'?'founder':'officer');}});
 svg.addEventListener('pointerleave',()=>{if(!down){let selected=featuresForGu().find(({ft})=>ft.properties.UNIT===stats.unit)?.ft.properties;panel.innerHTML=mapInfo(selected,stats.page==='founder'?'founder':'officer');}});
 svg.addEventListener('pointerdown',ev=>{if(ev.button!==0)return;down=true;move=false;downPath=ev.target.closest('path[data-geo]');prev=cursor(ev);svg.setPointerCapture(ev.pointerId);svg.classList.add('dragging');});
 svg.addEventListener('pointerup',ev=>{if(!down)return;down=false;svg.classList.remove('dragging');
   if(!move){let p=downPath?DATA.geo.features[Number(downPath.dataset.geo)].properties:findp(ev);if(p&&p.UNIT&&off[p.UNIT]){stats.unit=p.UNIT;render();}}});
 svg.addEventListener('pointercancel',()=>{down=false;svg.classList.remove('dragging');});
 svg.addEventListener('wheel',ev=>{ev.preventDefault();let p=cursor(ev);zoomAt(stats.zoom*(ev.deltaY<0?1.14:1/1.14),p.x,p.y);},{passive:false});
 document.getElementById('mapZoomIn').onclick=()=>zoomAt(stats.zoom*1.35);
 document.getElementById('mapZoomOut').onclick=()=>zoomAt(stats.zoom/1.35);
 document.getElementById('mapReset').onclick=()=>{stats.zoom=1;stats.panX=0;stats.panY=0;transform()};
}

render();
</script></body></html>'''
out=ROOT/'preview_quick_open.html'
out.write_text(HTML.replace('__DATA__',DATA),encoding='utf-8')
print('Generated',out, out.stat().st_size,'bytes')
