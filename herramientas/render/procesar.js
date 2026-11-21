const sharp=require('sharp'),fs=require('fs');
(async()=>{
for(const f of fs.readdirSync('/w/tmp/render')){
const k=f.replace('.png',''),src='/w/tmp/render/'+f;
const m=await sharp(src).metadata();
const ex=await sharp(src).extract({left:10,top:10,width:m.width-20,height:m.height-20}).toBuffer();
const tr=await sharp(ex).trim({background:'#ffffff',threshold:12}).toBuffer({resolveWithObject:true});
if(tr.info.width>=m.width-24||tr.info.height>=m.height-24)console.log('AVISO recortado',k);
const t=await sharp(tr.data).resize(656,656,{fit:'contain',background:'#ffffff'}).extend({top:72,bottom:72,left:72,right:72,background:'#ffffff'}).toBuffer();
let q=90,b;for(;;){b=await sharp(t).webp({quality:q}).toBuffer();if(b.length<=45000||q<=40)break;q-=5;}
fs.writeFileSync('/w/estaticos/imagenes/'+k+'.webp',b);console.log(k,tr.info.width+'x'+tr.info.height,b.length,'bytes q'+q);
}
})();
