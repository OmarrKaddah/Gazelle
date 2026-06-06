import _bootstrap  # noqa: F401
import sys
import json
import colorsys
from collections import defaultdict
from pathlib import Path
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, CORPUS_NAME

# Interactive community view (Cytoscape.js, the engine the frontend already uses).
# Communities are COMPOUND nodes — labelled boxes that physically contain their
# entities — so the grouping is explicit, not guessed from a force layout. One HTML:
#   - default "themes" mode: boxes collapsed to nodes, sized by members, linked by
#     aggregated cross-community relation weight; the global thematic map.
#   - "entities" toggle: boxes expand to show member entities + RELATED edges.
#   - tap any node: side panel shows the community's LLM summary (or entity details).
#
# Usage: python graphTraversal/plotCommunities.py <scope> [level]

OUT_DIR = Path('viz')


def runCypher(cypher, **params):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            return [dict(r) for r in session.run(cypher, **params)]


def palette(n):
    return ['#%02x%02x%02x' % tuple(int(c * 255) for c in colorsys.hsv_to_rgb(i / max(n, 1), 0.55, 0.9))
            for i in range(n)]


def fetch(corpus, level):
    entities = runCypher(
        '''MATCH (e:Entity)-[:IN_COMMUNITY]->(c:Community {corpus:$corpus, level:$level})
           RETURN e.canonicalId AS id, e.canonicalName AS name, e.type AS type, c.id AS comm''',
        corpus=corpus, level=level)
    communities = runCypher(
        '''MATCH (c:Community {corpus:$corpus, level:$level})
           OPTIONAL MATCH (e:Entity)-[:IN_COMMUNITY]->(c)
           RETURN c.id AS id, coalesce(c.title,c.id) AS title, coalesce(c.rating,0.0) AS rating,
                  coalesce(c.summary,'') AS summary, count(e) AS size''',
        corpus=corpus, level=level)
    entityIds = {e['id'] for e in entities}
    entityEdges = runCypher(
        '''UNWIND $ids AS aid
           MATCH (a:Entity {canonicalId:aid})-[r:RELATED]->(b:Entity)
           WHERE b.canonicalId IN $ids
           RETURN a.canonicalId AS src, b.canonicalId AS dst, coalesce(r.predicate,'') AS predicate,
                  coalesce(r.description,'') AS description''',
        ids=list(entityIds))
    commEdges = runCypher(
        '''MATCH (a:Entity)-[r:RELATED]->(b:Entity)
           MATCH (a)-[:IN_COMMUNITY]->(ca:Community {corpus:$corpus, level:$level})
           MATCH (b)-[:IN_COMMUNITY]->(cb:Community {corpus:$corpus, level:$level})
           WHERE ca.id < cb.id
           RETURN ca.id AS src, cb.id AS dst, sum(coalesce(r.weight,1)) AS weight''',
        corpus=corpus, level=level)
    return entities, communities, entityEdges, commEdges


def buildElements(entities, communities, entityEdges, commEdges):
    color = dict(zip([c['id'] for c in communities], palette(len(communities))))
    degree = defaultdict(int)
    for e in entityEdges:
        degree[e['src']] += 1
        degree[e['dst']] += 1
    ids = {e['id'] for e in entities}
    els = []
    for c in communities:
        els.append({'data': {'id': 'c::' + c['id'], 'kind': 'community', 'label': c['title'],
                             'color': color[c['id']], 'rating': round(c['rating'], 1),
                             'summary': c['summary'], 'size': c['size']}})
    for e in entities:
        els.append({'data': {'id': e['id'], 'parent': 'c::' + e['comm'], 'kind': 'entity',
                             'label': e['name'], 'color': color[e['comm']], 'type': e['type'],
                             'size': 8 + 3 * degree[e['id']]}})
    for r in entityEdges:
        if r['src'] in ids and r['dst'] in ids:
            els.append({'data': {'source': r['src'], 'target': r['dst'], 'predicate': r['predicate'],
                                'description': r['description']}, 'classes': 'eedge'})
    for e in commEdges:
        els.append({'data': {'source': 'c::' + e['src'], 'target': 'c::' + e['dst'], 'weight': e['weight']},
                   'classes': 'cedge'})
    return els


def html(corpus, level, elements):
    return TEMPLATE.replace('__TITLE__', f'{corpus} communities (level {level})').replace(
        '__ELEMENTS__', json.dumps(elements))


TEMPLATE = '''<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js"></script>
<script src="https://unpkg.com/layout-base/layout-base.js"></script>
<script src="https://unpkg.com/cose-base/cose-base.js"></script>
<script src="https://unpkg.com/cytoscape-fcose/cytoscape-fcose.js"></script>
<style>
 body{margin:0;font-family:system-ui,sans-serif;background:#0d0d10;color:#e8e8ea}
 #cy{position:absolute;left:0;top:42px;right:340px;bottom:0}
 #bar{position:absolute;left:0;top:0;height:42px;right:0;display:flex;gap:10px;align-items:center;padding:0 14px;background:#16161b;border-bottom:1px solid #2a2a31}
 #bar b{color:#9aa0ff}
 button{background:#2a2a35;color:#e8e8ea;border:1px solid #3a3a45;border-radius:6px;padding:6px 12px;cursor:pointer}
 button:hover{background:#34344a}
 #side{position:absolute;right:0;top:42px;bottom:0;width:340px;overflow:auto;padding:16px;background:#16161b;border-left:1px solid #2a2a31;box-sizing:border-box}
 #side h2{margin:0 0 6px;font-size:16px;color:#9aa0ff}
 #side .meta{color:#9a9aa6;font-size:12px;margin-bottom:10px}
 #side p{font-size:13px;line-height:1.5;color:#cfcfd6}
</style></head><body>
<div id="bar"><b>__TITLE__</b>
 <button id="toggle">Show entities</button>
 <button id="relayout">Re-layout</button>
 <span id="mode" style="color:#9a9aa6"></span>
</div>
<div id="cy"></div>
<div id="side"><h2>Click a community</h2><p>Boxes are communities. Tap one to read its summary; toggle to expand into its entities.</p></div>
<script>
const elements = __ELEMENTS__;
const cy = cytoscape({container:document.getElementById('cy'), elements,
 style:[
  {selector:'node[kind="community"]', style:{'label':'data(label)','shape':'round-rectangle',
    'background-color':'data(color)','background-opacity':0.12,'border-color':'data(color)','border-width':2,
    'color':'#fff','font-size':14,'font-weight':'bold','text-valign':'top','text-halign':'center',
    'text-margin-y':-4,'text-wrap':'ellipsis','text-max-width':'130px',
    'padding':'18px','width':'mapData(size,1,80,28,100)','height':'mapData(size,1,80,28,100)'}},
  {selector:'node[kind="entity"]', style:{'label':'data(label)','background-color':'data(color)',
    'width':'data(size)','height':'data(size)','font-size':11,'color':'#cdcdd6','min-zoomed-font-size':16}},
  {selector:'edge.eedge', style:{'width':1,'line-color':'#3a3a45','curve-style':'straight','opacity':0.55,
    'label':'data(predicate)','font-size':9,'min-zoomed-font-size':13,'color':'#9a9aa6','text-rotation':'autorotate',
    'text-background-color':'#0d0d10','text-background-opacity':0.75,'text-background-padding':'2px'}},
  {selector:'edge.cedge', style:{'width':'mapData(weight,1,40,1,10)','line-color':'#5a5a8a','opacity':0.7,'curve-style':'bezier'}},
  {selector:'.hidden', style:{'display':'none'}},
  {selector:':selected', style:{'border-width':4,'border-color':'#fff'}}
 ]});

function layout(){cy.layout({name:'fcose',quality:'proof',randomize:true,animate:false,
  packComponents:true,nodeDimensionsIncludeLabels:true,
  nodeSeparation:160,idealEdgeLength:110,nodeRepulsion:24000,gravity:0.12,gravityCompound:2.0,
  numIter:3000,tilingPaddingVertical:30,tilingPaddingHorizontal:30}).run();cy.fit(undefined,40);}

let showEntities=false;
function applyMode(){
 if(showEntities){cy.elements('.cedge').addClass('hidden');cy.elements('node[kind="entity"], .eedge').removeClass('hidden');
   document.getElementById('toggle').textContent='Show themes';document.getElementById('mode').textContent='entities — boxes hold their members';}
 else{cy.elements('node[kind="entity"], .eedge').addClass('hidden');cy.elements('.cedge').removeClass('hidden');
   document.getElementById('toggle').textContent='Show entities';document.getElementById('mode').textContent='themes — '+cy.elements('node[kind="community"]').length+' communities';}
 layout();
}
document.getElementById('toggle').onclick=()=>{showEntities=!showEntities;applyMode();};
document.getElementById('relayout').onclick=layout;

cy.on('tap','node',evt=>{const d=evt.target.data();const s=document.getElementById('side');
 if(d.kind==='community'){s.innerHTML=`<h2>${d.label}</h2><div class="meta">rating ${d.rating} · ${d.size} entities</div><p>${d.summary||'(no summary)'}</p>`;}
 else{s.innerHTML=`<h2>${d.label}</h2><div class="meta">${d.type}</div><p>entity in community <b>${cy.getElementById(d.parent).data('label')}</b></p>`;}
});
cy.on('tap','edge',evt=>{const d=evt.target.data();const s=document.getElementById('side');
 const src=cy.getElementById(d.source).data('label'),dst=cy.getElementById(d.target).data('label');
 if(d.predicate!==undefined){s.innerHTML=`<h2>${src} → ${dst}</h2><div class="meta">${d.predicate||'related'}</div><p>${d.description||'(no description)'}</p>`;}
 else{s.innerHTML=`<h2>${src} ↔ ${dst}</h2><div class="meta">cross-community relation weight ${d.weight}</div>`;}
});
applyMode();
</script></body></html>'''


def main():
    corpus = sys.argv[1] if len(sys.argv) > 1 else CORPUS_NAME
    level = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    OUT_DIR.mkdir(exist_ok=True)
    entities, communities, entityEdges, commEdges = fetch(corpus, level)
    elements = buildElements(entities, communities, entityEdges, commEdges)
    out = OUT_DIR / f'{corpus}_communities.html'
    out.write_text(html(corpus, level, elements), encoding='utf-8')
    print(f'[plotCommunities] {corpus} L{level}: {len(communities)} communities, {len(entities)} entities, '
          f'{len(commEdges)} theme links -> {out}')


if __name__ == '__main__':
    main()
