const s=require('sharp'),fs=require('fs');
(async()=>{
for(const f of fs.readdirSync(process.argv[2])){
const {data,info}=await s(process.argv[2]+'/'+f).removeAlpha().greyscale().resize(56,28,{fit:'fill'}).raw().toBuffer({resolveWithObject:true});
console.log('== '+f);
for(let y=0;y<28;y++){let l='';for(let x=0;x<56;x++){const v=data[(y*info.width+x)*info.channels];l+=v>=252?' ':v>215?'.':v>150?'o':'#';}console.log(l);}
}
})();
