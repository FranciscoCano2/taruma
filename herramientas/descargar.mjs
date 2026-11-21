import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { pipeline } from 'node:stream/promises';
import { Readable } from 'node:stream';
const base = '/w/originales';
const slugs = process.argv.slice(2);
const md5 = f => new Promise((ok, ko) => { const h = crypto.createHash('md5'); fs.createReadStream(f).on('data', d => h.update(d)).on('end', () => ok(h.digest('hex'))).on('error', ko); });
const pausa = ms => new Promise(r => setTimeout(r, ms));
async function bajar(url, dest, size, hash) {
  for (let i = 1; i <= 5; i++) {
    try {
      if (fs.existsSync(dest) && fs.statSync(dest).size === size && await md5(dest) === hash) return 'ya estaba';
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      const r = await fetch(url, { signal: AbortSignal.timeout(900000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await pipeline(Readable.fromWeb(r.body), fs.createWriteStream(dest));
      if (fs.statSync(dest).size !== size) throw new Error('tamaño distinto');
      if (await md5(dest) !== hash) throw new Error('md5 distinto');
      return 'ok ' + size;
    } catch (e) { console.log('  reintento', i, e.message); await pausa(3000 * i); }
  }
  throw new Error('falló ' + url);
}
const json = async u => (await fetch(u, { signal: AbortSignal.timeout(60000) })).json();
const fallas = [];
for (const slug of slugs) {
  try {
    console.log('==', slug);
    const f = await json('https://api.polyhaven.com/files/' + slug);
    const g = f.gltf['1k'].gltf;
    const dir = base + '/' + slug;
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(dir + '/info.json', JSON.stringify(await json('https://api.polyhaven.com/info/' + slug), null, 1));
    console.log(' ', slug + '.gltf', await bajar(g.url, dir + '/' + slug + '.gltf', g.size, g.md5));
    for (const [rel, inc] of Object.entries(g.include || {})) {
      if (rel.includes('..')) throw new Error('ruta rara ' + rel);
      console.log(' ', rel, await bajar(inc.url, dir + '/' + rel, inc.size, inc.md5));
    }
  } catch (e) { console.log('FALLA', slug, e.message); fallas.push(slug); }
}
const todos = await json('https://api.polyhaven.com/assets?t=models');
console.log('Candidatas Poly Haven para la taza (09):', Object.keys(todos).filter(k => /cup|mug/i.test(k + ' ' + todos[k].name)).join(', ') || 'ninguna');
console.log('FIN. Fallas:', fallas.join(', ') || 'ninguna');
