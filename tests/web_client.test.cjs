const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

async function browser() {
  const nodes = new Map();
  function element() {
    return {value:'', textContent:'', hidden:false, disabled:false, children:[], handlers:{},
      classList:{toggle(){}}, addEventListener(name, fn){this.handlers[name]=fn;},
      setAttribute(){}, append(...children){this.children.push(...children);},
      replaceChildren(...children){this.children=children; if(children[0]?.value) this.value=children[0].value;},
      click(){return this.handlers.click?.();}};
  }
  const get = id => {if(!nodes.has(id)) nodes.set(id,element()); return nodes.get(id);};
  get('latitude').value='42.37';get('longitude').value='-72.28';get('radius').value='25';
  const context=vm.createContext({document:{getElementById:get,createElement:element,querySelector:()=>element(),body:element()},
    window:{}, console, Date, Number, Object, String, Math, JSON, Error,
    Option:function(name,value){this.value=value;this.textContent=name;},
    fetch:async()=>({ok:true,json:async()=>({token:'token',regions:[{code:'MA',name:'Massachusetts',center:[42.37,-72.28],species:['Bobcat']}]})}),
    setTimeout:()=>0,setInterval:()=>0,clearInterval(){}});
  vm.runInContext(fs.readFileSync('wildlocate/web/app.js','utf8'),context);
  await new Promise(resolve=>setImmediate(resolve));
  return {context,get,run:code=>vm.runInContext(code,context)};
}
const complete={status:'complete',result:{species:'Bobcat',score:.5,percentile:50,category:'Moderate',model:'Test',training_observations:25,latitude:42.37,longitude:-72.28,features:{}}};
const response=data=>({ok:true,status:200,json:async()=>data});

test('Cancel suppresses a completion response already in flight',async()=>{
  const b=await browser();
  let completePoll,completeCancel;
  b.context.fetch=path=>new Promise(resolve=>{if(path.endsWith('/cancel'))completeCancel=resolve;else completePoll=resolve;});
  b.run("clearResult();activeJob='job';setBusy(true)");
  const polling=b.run("poll('job',revision)");
  const cancelling=b.get('cancel').handlers.click();
  completePoll(response(complete));await polling;
  completeCancel(response({status:'complete'}));await cancelling;
  assert.equal(b.get('result').hidden,true);
  assert.equal(b.get('inputs').disabled,false);
});

test('A missing job releases controls instead of polling forever',async()=>{
  const b=await browser();
  b.context.fetch=async()=>({ok:false,status:404,json:async()=>({error:'Analysis not found.'})});
  b.run("clearResult();activeJob='missing';setBusy(true)");
  await b.run("poll('missing',revision)");
  assert.equal(b.get('inputs').disabled,false);
  assert.equal(b.get('cancel').hidden,true);
  assert.match(b.get('error').textContent,/not found/i);
});
