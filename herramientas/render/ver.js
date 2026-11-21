const h=require('http'),fs=require('fs');
const fig=f=>'<figure style="display:inline-block;margin:6px"><img src="'+f+'" width="380" style="background:#fff"><figcaption>'+f+'</figcaption></figure>';
h.createServer((q,r)=>{
const u=decodeURIComponent(q.url.slice(1));
if(u===''){r.setHeader('content-type','text/html');return r.end('<body style="background:#ccc;font:14px sans-serif">'+fs.readdirSync('/s').filter(f=>f.endsWith('.png')).map(fig).join(''));}
if(/^[a-z0-9_]+\.png$/.test(u)&&fs.existsSync('/s/'+u)){r.setHeader('content-type','image/png');return fs.createReadStream('/s/'+u).pipe(r);}
r.statusCode=404;r.end();
}).listen(8000);
