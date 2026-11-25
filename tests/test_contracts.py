from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data_access import read_files, load_geometry,map_features
from map_views import color_of, ENTRY, SURV,OUT_SCOPE,GRAY,founder_band,status_label

def test_real_data_contract():
    officer,founder,mapping=read_files()
    assert len(officer)==144 and len(founder)==144 and len(mapping)==328
    assert officer.diagnosis_scope.eq('진단 (7개 구 정체 동)').sum()==65
    assert officer.diagnosis_scope.eq('현황만 (정체 동 아님)').sum()==65
    assert officer.diagnosis_scope.eq('현황만 (읍·면, 진단 범위 밖)').sum()==14
    assert (officer.bottleneck=='생존 병목').sum()==34
    assert (officer.bottleneck=='진입 병목').sum()==31
    assert set(founder.unit)==set(officer.unit)
    rural=officer[officer.gu.isin({'달성군','군위군'})]
    assert len(rural)==14 and rural.bottleneck.isna().all() and rural.confidence.isna().all()
    assert rural.n_active.notna().all() and rural.growth_past3.notna().all()
    assert officer.loc[officer.gu.eq('군위군'),'pop3'].isna().all()

def test_boundaries_are_explicitly_administrative_until_team_supplies_legal():
    o,f,m=read_files(); geo,mode=load_geometry(); joined,stats=map_features(o,f,m,geo,mode)
    assert mode=='admin-preview' and len(joined['features'])==150
    assert all(ft['properties']['MAP_MODE']=='admin-preview' for ft in joined['features'])
    assert stats['collisions']>0
    assert any(ft['properties']['UNIT'].startswith('달성군 ') for ft in joined['features'])
    assert any(ft['properties']['UNIT'].startswith('군위군 ') for ft in joined['features'])

def test_confidence_and_scope_control_diagnosis_color():
    for group,palette in [('진입 병목',ENTRY),('생존 병목',SURV)]:
        for conf,color in palette.items():
            assert color_of({'diagnosis_scope':'진단 (7개 구 정체 동)','bottleneck':group,'confidence':conf},'diagnosis')==color
    assert color_of({'diagnosis_scope':'현황만 (읍·면, 진단 범위 밖)'},'diagnosis')==OUT_SCOPE
    assert color_of({'diagnosis_scope':'현황만 (정체 동 아님)'},'diagnosis')==GRAY
    assert status_label({'diagnosis_scope':'현황만 (읍·면, 진단 범위 밖)'})=='진단 범위 밖 · 현황만'
    assert founder_band(.579)==0 and founder_band(.63)==2 and founder_band(.73)==4
