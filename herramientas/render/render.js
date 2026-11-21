const http=require('http'),fs=require('fs');
const puppeteer=require('puppeteer-core');
const W='/w/herramientas/mv/node_modules/';
const est={'/mv.js':W+'@google/model-viewer/dist/model-viewer.min.js','/meshopt.js':W+'../meshopt_umd.js'};
const pagina='<!doctype html><meta charset=utf-8><style>html,body{margin:0;overflow:hidden;background:#fff}model-viewer{display:block;width:1600px;height:1600px}</style><script type=module>import "/mv.js";await customElements.whenDefined("model-viewer");const C=customElements.get("model-viewer");C.meshoptDecoderLocation="/meshopt.js";const m=new C();m.setAttribute("src","/m/"+location.hash.slice(1)+".glb");for(const[a,v]of Object.entries({"camera-orbit":"35deg 72deg auto","environment-image":"neutral","exposure":"1.1","shadow-intensity":"0","interaction-prompt":"none"}))m.setAttribute(a,v);m.addEventListener("load",async()=>{await new Promise(r=>setTimeout(r,800));window.__ok=1;});m.addEventListener("error",e=>window.__err=String(e.detail&&e.detail.sourceError||"error"));document.body.append(m);</script>';
const srv=http.createServer((q,r)=>{
const u=q.url.split('?')[0];let f=null,t='text/javascript';
if(u==='/'){r.setHeader('content-type','text/html');return r.end(pagina);}
if(est[u])f=est[u];else if(/^\/m\/[a-z0-9_]+\.glb$/.test(u)){f='/w/estaticos/modelos/'+u.slice(3);t='model/gltf-binary';}
if(!f||!fs.existsSync(f)){r.statusCode=404;return r.end();}
r.setHeader('content-type',t);fs.createReadStream(f).pipe(r);
}).listen(8123);
(async()=>{
const claves=process.argv.length>2?process.argv.slice(2):fs.readdirSync('/w/estaticos/modelos').map(f=>f.replace('.glb',''));
const b=await puppeteer.launch({executablePath:process.env.PUPPETEER_EXECUTABLE_PATH||'/usr/bin/chromium-browser',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
for(const k of claves){
const p=await b.newPage();await p.setViewport({width:1600,height:1600,deviceScaleFactor:2});
p.on('console',m=>{if(m.type()==='error')console.log(' consola:',m.text())});p.on('pageerror',e=>console.log(' error:',e.message));
await p.goto('http://localhost:8123/#'+k);
try{await p.waitForFunction('window.__ok||window.__err',{timeout:120000});}catch(e){}
if(!await p.evaluate('window.__ok')){console.log('FALLA',k,await p.evaluate('window.__err'));await p.close();continue;}
await new Promise(r=>setTimeout(r,1500));
const buf=await p.screenshot({type:'png'});
fs.writeFileSync('/w/tmp/render/'+k+'.png',buf);console.log(k,buf.length,'bytes');await p.close();
}
await b.close();srv.close();
})();
