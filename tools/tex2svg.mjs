// TeX -> self-describing SVG JSON using MathJax (TeX -> SVG), with every
// MathML node indexed so the Python engine can animate sub-expressions.
import { mathjax } from 'mathjax-full/js/mathjax.js';
import { TeX } from 'mathjax-full/js/input/tex.js';
import { SVG } from 'mathjax-full/js/output/svg.js';
import { liteAdaptor } from 'mathjax-full/js/adaptors/liteAdaptor.js';
import { RegisterHTMLHandler } from 'mathjax-full/js/handlers/html.js';
import { AllPackages } from 'mathjax-full/js/input/tex/AllPackages.js';
import { SerializedMmlVisitor } from 'mathjax-full/js/core/MmlTree/SerializedMmlVisitor.js';
import fs from 'fs';

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const tex = new TeX({ packages: AllPackages, inlineMath: [['$', '$']] });
const svg = new SVG({ fontCache: 'local' });
const doc = mathjax.document('', { InputJax: tex, OutputJax: svg });

// Simple 2D affine helpers: [a,b,c,d,e,f]
const mul = (m, n) => [
  m[0]*n[0]+m[2]*n[1], m[1]*n[0]+m[3]*n[1],
  m[0]*n[2]+m[2]*n[3], m[1]*n[2]+m[3]*n[3],
  m[0]*n[4]+m[2]*n[5]+m[4], m[1]*n[4]+m[3]*n[5]+m[5],
];
const parseTransform = (t) => {
  let m = [1,0,0,1,0,0];
  if (!t) return m;
  const re = /(\w+)\s*\(([^)]*)\)/g; let r;
  while ((r = re.exec(t))) {
    const v = r[2].split(/[\s,]+/).filter(s=>s.length).map(Number);
    let n = [1,0,0,1,0,0];
    if (r[1] === 'translate') n = [1,0,0,1, v[0]||0, v[1]||0];
    else if (r[1] === 'scale') n = [v[0],0,0,(v[1]===undefined?v[0]:v[1]),0,0];
    else if (r[1] === 'matrix') n = v;
    else if (r[1] === 'rotate') {
      const a=(v[0]||0)*Math.PI/180, ca=Math.cos(a), sa=Math.sin(a);
      n=[ca,sa,-sa,ca,0,0];
      if (v.length>2){ n = mul([1,0,0,1,v[1],v[2]], mul(n,[1,0,0,1,-v[1],-v[2]])); }
    }
    m = mul(m, n);
  }
  return m;
};
const fnum = (x) => (Math.abs(x) < 1e-9 ? '0' : +x.toFixed(3)).toString();

function nodeId(el, path) { return path; }

// Linearise an SVG element subtree into primitives with baked transforms.
function flatten(el, ctm, defs, out, path, counter, opts) {
  const tag = el.kind;
  const cls = el.attributes && el.attributes['data-mml-node'] ? el.attributes['data-mml-node'].split(' ')[0] : null;
  const m = mul(ctm, parseTransform(el.attributes && el.attributes.transform));
  let p = path;
  if (cls) p = path + '/' + cls;
  if (tag === '#text') return;
  if (tag === 'rect') {
    const a = el.attributes; const x=+(a.x||0), y=+(a.y||0), w=+(a.width||0), h=+(a.height||0);
    if (w>0 && h>0) {
      const pts = [[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(([px,py]) => [m[0]*px+m[2]*py+m[4], m[1]*px+m[3]*py+m[5]]);
      const d = 'M ' + pts.map((q)=>q.map(fnum).join(' ')).join(' L ') + ' Z';
      out.push({ t: 'path', d, fill: a.fill || opts.defaultFill, key: p, id: ++counter.n });
    }
    return;
  }
  if (tag === 'use') {
    const href = (el.attributes['xlink:href'] || el.attributes.href || '').replace(/^#/, '');
    const ref = defs[href];
    if (ref) {
      // `use` shifts by x/y attributes, then the path is defined in font units.
      const a = el.attributes;
      const mm = mul(m, [1,0,0,1, +(a.x||0), +(a.y||0)]);
      // store transform separately so the caller can place it precisely
      out.push({ t: 'path', d: ref.d, fill: a.fill || opts.defaultFill, key: p,
                 id: ++counter.n, matrix: mm.map(fnum).map(Number) });
    }
    return;
  }
  if (tag === 'path') {
    out.push({ t: 'path', d: el.attributes.d, fill: el.attributes.fill || opts.defaultFill, key: p, id: ++counter.n, matrix: m.map(fnum).map(Number) });
    return;
  }
  const kids = el.children || [];
  for (const k of kids) {
    if (k.kind === 'defs') continue;   // glyph definitions must not be drawn directly
    flatten(k, m, defs, out, p, counter, opts);
  }
}

function convert(texString, opts = {}) {
  const node = doc.convert(texString, { display: opts.display !== false, em: 16, ex: 8, containerWidth: 80*16 });
  const svgEl = adaptor.firstChild(node); // <svg>
  const viewBox = (svgEl.attributes.viewBox || '0 0 1000 1000').split(/\s+/).map(Number);
  // Collect <defs> glyph paths
  const defs = {};
  const walkDefs = (el) => {
    if (el.kind === 'path' && el.attributes && el.attributes.id) defs[el.attributes.id] = { d: el.attributes.d };
    (el.children||[]).forEach(walkDefs);
  };
  walkDefs(svgEl);
  const out = []; const counter = { n: 0 };
  flatten(svgEl, [1,0,0,1,0,0], defs, out, '', counter, { defaultFill: 'currentColor' });
  // MathJax units: 1000 per em.
  return {
    tex: texString,
    viewBox,
    width_em: (viewBox[2]) / 1000,
    height_em: (viewBox[3]) / 1000,
    baseline_em: (viewBox[1] + viewBox[3]) / 1000, // distance from top to baseline
    paths: out,
  };
}

const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const results = jobs.map((j) => {
  try { return { key: j.key, ok: true, svg: convert(j.tex, j) }; }
  catch (e) { return { key: j.key, ok: false, error: String(e) }; }
});
fs.writeFileSync(process.argv[3], JSON.stringify(results, null, 0));
console.log('converted', results.filter(r=>r.ok).length, 'of', results.length);
