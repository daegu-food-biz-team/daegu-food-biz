"""True GeoJSON geometries with a conspicuously labelled temporary HJD proxy."""
from __future__ import annotations
import json
import folium
from branca.element import MacroElement
from jinja2 import Template
from data_access import bound_extent

ENTRY={'높음':'#1F4FB8','보통':'#7898D6','낮음':'#CDD9F1'}
SURV={'높음':'#C65A11','보통':'#E5A16F','낮음':'#F4D7C1'}
FOUNDER_COLORS=['#AC4C58','#E3A071','#DCE0E3','#88A9CE','#315FA8']
GRAY='#C4CDD8';OUT_SCOPE='#A7B0BB';NO_DATA='#E4E8EC'

def founder_band(val):
    if val is None:return -1
    if val < .58:return 0
    if val < .63:return 1
    if val < .69:return 2
    if val < .73:return 3
    return 4

def status_label(rec):
    if not rec:return '분석 미제공'
    scope=rec.get('diagnosis_scope','')
    if scope.startswith('현황만 (읍·면'):return '진단 범위 밖 · 현황만'
    if scope.startswith('현황만'):return '정체 동 아님 · 현황만'
    return rec['bottleneck'] or '분석 미제공'

def color_of(rec,mode,founder=None):
    if mode=='founder':
        if not founder:return NO_DATA
        band=founder_band(founder.get('surv2_adj'))
        return FOUNDER_COLORS[band] if band>=0 else NO_DATA
    if not rec:return NO_DATA
    if mode=='status':
        g=rec.get('growth_past3')
        if g is None:return NO_DATA
        if g < -.10:return '#B94C54'
        if g < -.03:return '#E3A5A5'
        if g < .03:return '#E9ECEF'
        if g < .10:return '#A6BEDB'
        return '#3865A9'
    if rec.get('diagnosis_scope','').startswith('현황만 (읍·면'):return OUT_SCOPE
    if rec.get('diagnosis_scope','').startswith('현황만'):return GRAY
    palette=ENTRY if rec['bottleneck']=='진입 병목' else SURV
    return palette.get(rec['confidence'],NO_DATA)

class FixedMapControls(MacroElement):
    """Leaflet fixed hover info + reset-extent + optional small-sample diagonal hatch."""
    def __init__(self,geo_name,bounds,selected_unit='',hatch=False):
        super().__init__()
        self._name='FixedMapControls'
        self.geo_name=geo_name
        self.bounds_js=json.dumps(bounds)
        self.selected_js=json.dumps(selected_unit,ensure_ascii=False)
        self.hatch=hatch
        self._template=Template(r"""
        {% macro script(this, kwargs) %}
        (function(){
          var map={{this._parent.get_name()}}, geo={{this.geo_name}};
          var bounds={{this.bounds_js | safe}};
          var chosen={{this.selected_js | safe}};
          function esc(str){return String(str===undefined || str===null?'':str).replace(/[&<>\"']/g,function(ch){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[ch]||ch;});}
          var info=L.control({position:'topright'});
          info.onAdd=function(){this._div=L.DomUtil.create('div','dfb-fixed-info');L.DomEvent.disableClickPropagation(this._div);this.update(null);return this._div;};
          info.update=function(p){
            if(!p){this._div.innerHTML='<div class="dfb-fixed-heading">지역 정보</div><div class="dfb-fixed-idle">동 위에 마우스를 올려 주세요</div>';return;}
            var analysis=p.ANALYSIS || '분석 미제공';
            this._div.innerHTML='<div class="dfb-fixed-heading">지역 정보</div>'+
             '<div class="dfb-fixed-row"><span>지역</span><b>'+esc(p.UNIT || p.PHYSICAL_NAME)+'</b></div>'+
             '<div class="dfb-fixed-row"><span>지역코드</span><b>'+esc(p.CODE)+'</b></div>'+
             '<div class="dfb-fixed-row"><span>분석</span><b>'+esc(analysis)+'</b></div>'+
             (p.MAP_MODE==='admin-preview'?'<div class="dfb-fixed-foot">임시 행정동 경계 · 코드도 행정동 코드'+(p.OVERLAP>0?'<br>다른 법정동 '+p.OVERLAP+'곳과 동일 영역 공유':'')+'</div>':'');
          };
          info.addTo(map);
          var reset=L.control({position:'topleft'});
          reset.onAdd=function(){var b=L.DomUtil.create('button','dfb-map-reset'); b.type='button';b.innerHTML='대구 전체 ↺';b.title='대구 전체 보기';
            L.DomEvent.disableClickPropagation(b);L.DomEvent.on(b,'click',function(e){L.DomEvent.stop(e);map.fitBounds(bounds,{padding:[12,12]});});return b;};
          reset.addTo(map);
          geo.eachLayer(function(layer){
            var p=layer.feature.properties;
            layer.on('mouseover',function(){info.update(p);layer.setStyle({weight:2,color:'#16191d',fillOpacity:.96});layer.bringToFront();});
            layer.on('mouseout',function(){info.update(null);geo.resetStyle(layer);});
            layer.on('click',function(){info.update(p);});
            if(p.UNIT===chosen){info.update(p);}
          });
          {% if this.hatch %}
          function applyHatch(){
            var svg=map.getPanes().overlayPane.querySelector('svg');if(!svg)return;
            var id='dfb-hatch-{{this.get_name()}}';
            var defs=svg.querySelector('defs');
            if(!defs){defs=document.createElementNS('http://www.w3.org/2000/svg','defs');svg.insertBefore(defs,svg.firstChild);}
            geo.eachLayer(function(layer){
              var p=layer.feature.properties;
              if(!p.SMALL_SAMPLE || !layer._path)return;
              var color=p.FILL;
              var key=id+'-'+color.replace(/[^a-zA-Z0-9]/g,'');
              if(!document.getElementById(key)){
                var pat=document.createElementNS('http://www.w3.org/2000/svg','pattern');
                pat.setAttribute('id',key);pat.setAttribute('patternUnits','userSpaceOnUse');pat.setAttribute('width','7');pat.setAttribute('height','7');
                pat.setAttribute('patternTransform','rotate(45)');
                var bg=document.createElementNS('http://www.w3.org/2000/svg','rect');bg.setAttribute('width','7');bg.setAttribute('height','7');bg.setAttribute('fill',color);
                var line=document.createElementNS('http://www.w3.org/2000/svg','path');line.setAttribute('d','M 0 0 L 0 7');line.setAttribute('stroke','#41464c');line.setAttribute('stroke-width','1.6');
                pat.appendChild(bg);pat.appendChild(line);defs.appendChild(pat);
              }
              layer._path.style.fill='url(#'+key+')';
            });
          }
          applyHatch(); map.on('zoomend moveend',applyHatch);
          {% endif %}
        })();
        {% endmacro %}
        """)

def build_map(features, officer, founder, role, layer_mode, selected_unit,gu='대구 전체'):
    lookup_o={r['unit']:r for r in officer.to_dict('records')}
    lookup_f={r['unit']:r for r in founder.to_dict('records')}
    filtered=[]
    for feat in features['features']:
        p=feat['properties'].copy();unit=p.get('UNIT','')
        rec=lookup_o.get(unit)
        founder_rec=lookup_f.get(unit)
        if gu!='대구 전체':
            if p['MAP_MODE']=='legal':
                if not unit.startswith(gu+' '):continue
            elif gu not in p.get('PHYSICAL_NAME',''):
                continue
        mode='founder' if role=='founder' else layer_mode
        p['FILL']=color_of(rec,mode,founder_rec)
        p['SMALL_SAMPLE']=bool(founder_rec.get('small_sample',False)) if role=='founder' and founder_rec else False
        if role=='founder':
            p['ANALYSIS']=(f"카페 개업 후 2년 생존율 {founder_rec['surv2_adj']*100:.1f}%" if founder_rec else '카페 자료 없음')
        elif layer_mode=='status':
            p['ANALYSIS']=(f"3년 점포 증감 {rec['growth_past3']:+.1%} · 현황" if rec else '현황 미제공')
        else:p['ANALYSIS']=status_label(rec)+(f" · 확신도 {rec['confidence']}" if rec and rec.get('diagnosis_scope','').startswith('진단') else '')
        p['SELECTED']=unit==selected_unit
        filtered.append({'type':'Feature','geometry':feat['geometry'],'properties':p})
    geo={'type':'FeatureCollection','features':filtered}
    # The visible polygon set controls both the initial viewport and movement limits.
    # Do not fit the entire city after a user filters to a single district.
    bounds=bound_extent(geo if filtered else features)
    south,west=bounds[0]; north,east=bounds[1]
    margin_lat=max((north-south)*.22,.0008)
    margin_lon=max((east-west)*.22,.0008)
    max_bounds=[[south-margin_lat,west-margin_lon],[north+margin_lat,east+margin_lon]]
    m=folium.Map(location=[(south+north)/2,(west+east)/2],tiles=None,control_scale=False,
        zoom_start=10,prefer_canvas=False,zoom_control=True,
        min_zoom=9,max_zoom=16,scroll_wheel_zoom=True)
    m.options['maxBounds']=max_bounds
    m.options['maxBoundsViscosity']=1.0
    m.fit_bounds(bounds,padding=(26,26))
    def style(f):
        p=f['properties'];chosen=p['SELECTED']
        return {'fillColor':p['FILL'],'color':'#16191d' if chosen else '#FFFFFF',
                'weight':2.2 if chosen else .85,'fillOpacity':.92 if chosen else .88,
                'dashArray':'3,3' if role=='founder' and p['SMALL_SAMPLE'] else None}
    gj=folium.GeoJson(geo,name='지도 경계',style_function=style,
                      highlight_function=lambda f:{'weight':2,'color':'#111111','fillOpacity':.95})
    gj.add_to(m)
    FixedMapControls(gj.get_name(),bounds,selected_unit,hatch=(role=='founder')).add_to(m)
    m.get_root().header.add_child(folium.Element('''<style>
    .dfb-fixed-info{width:216px;box-sizing:border-box;background:rgba(255,255,255,.97);border:1px solid #c9ced4;box-shadow:0 2px 12px #0000000b;padding:12px 13px;font-family:Arial,sans-serif;font-size:11px;color:#1d2024;}
    .dfb-fixed-heading{font-weight:800;font-size:12px;padding-bottom:7px;border-bottom:1px solid #e4e7ea;margin-bottom:6px;}
    .dfb-fixed-row{display:flex;justify-content:space-between;gap:10px;line-height:1.5;padding:3px 0;}
    .dfb-fixed-row span{color:#737982;white-space:nowrap;}.dfb-fixed-row b{font-weight:700;text-align:right;overflow-wrap:anywhere;}
    .dfb-fixed-foot{border-top:1px solid #ebedf0;margin-top:7px;padding-top:5px;color:#818891;line-height:1.5;font-size:10px;}
    .dfb-fixed-idle{color:#747980;padding:4px 0}.dfb-map-reset{border:1px solid #c7cbd0;background:#fff;padding:7px 10px;font-size:11px;font-weight:bold;cursor:pointer;}
    .leaflet-container{background:#F6F7F8!important;}.leaflet-control-attribution{font-size:9px!important;}
    .leaflet-control-zoom a{background:#fff!important;color:#1a1a1a!important;border-color:#c9cdd2!important;}
    </style>'''))
    return m,geo
