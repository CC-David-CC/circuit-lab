import './style.css';
import { EXAMPLES, validateNetlist } from './netlist.mjs';

export function mount(host) {
  const operations = host.documentOperations; if (!operations) throw Error('Document operation service is required.');
  const { make, textButton } = host.ui, { mirrorFileContext, signedInSubject } = host.storage;
  const owner = signedInSubject(), body = make('div','window-content circuit-lab'), toolbar = make('div','circuit-toolbar');
  const source = document.createElement('textarea'); source.className = 'circuit-source'; source.spellcheck = false; source.value = EXAMPLES.divider; source.setAttribute('aria-label','SPICE netlist');
  const path = document.createElement('input'); path.value = '/Circuit-' + crypto.randomUUID() + '.cir'; path.setAttribute('aria-label','Circuit file path');
  const status = make('p','circuit-status','Choose an example or open a SPICE netlist.'), table = make('pre','circuit-results'), canvas = document.createElement('canvas');
  canvas.width = 900; canvas.height = 300; canvas.setAttribute('aria-label','Circuit simulation plot'); canvas.hidden = true;
  const input = document.createElement('input'); input.type = 'file'; input.accept = '.cir,.sp,.spice,.txt'; input.setAttribute('aria-label','Upload circuit file');
  let disposed = false, worker = null, generation = 0, timer = null, version = null, savedPath = null, dirty = false, busy = false, revision = 0, documentEpoch = 0;
  const valid = () => !disposed && !host.signal.aborted && owner === signedInSubject();
  const tell = text => { if (valid()) status.textContent = text; };
  const cancel = () => { generation++; worker?.terminate(); worker = null; clearTimeout(timer); timer = null; };
  function plot(series) {
    canvas.hidden = true;
    const x = series.find(s => ['time','frequency'].includes(s.type)) || series.find(s => ['time','frequency'].includes(s.name));
    const y = series.find(s => s.type === 'voltage' && s !== x);
    if (!x || !y || x.values.length < 2) return;
    const magnitude = v => typeof v === 'number' ? v : Math.hypot(v?.real || 0,v?.img || 0);
    const pairs = x.values.map((v,i) => [magnitude(v), magnitude(y.values[i])]).filter(v => v.every(Number.isFinite));
    if (pairs.length < 2) return;
    const xmin = Math.min(...pairs.map(p=>p[0])), xmax = Math.max(...pairs.map(p=>p[0]));
    const ymin = Math.min(...pairs.map(p=>p[1])), ymax = Math.max(...pairs.map(p=>p[1]));
    const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height, left=75, top=20, right=20, bottom=40;
    ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#768392';ctx.strokeRect(left,top,w-left-right,h-top-bottom);
    ctx.fillStyle='#243142';ctx.font='16px sans-serif';ctx.fillText(y.name + (typeof y.values[0] === 'number' ? '' : ' magnitude'),left,16);ctx.fillText(x.name,left,h-8);
    ctx.fillText(ymax.toPrecision(4),4,top+9);ctx.fillText(ymin.toPrecision(4),4,h-bottom);
    ctx.strokeStyle='#2265b0';ctx.lineWidth=2;ctx.beginPath();pairs.forEach(([a,b],i)=>{const px=left+(a-xmin)/(xmax-xmin||1)*(w-left-right),py=top+(ymax-b)/(ymax-ymin||1)*(h-top-bottom);i?ctx.lineTo(px,py):ctx.moveTo(px,py)});ctx.stroke();canvas.hidden=false;
  }
  function run() {
    try { validateNetlist(source.value); } catch(e) { tell(e.message); return; }
    cancel(); const current = generation; table.textContent=''; canvas.hidden=true; tell('Starting the browser-local ngspice solver…');
    worker = new Worker(new URL('./workers/spice.mjs',import.meta.url),{type:'module'});
    timer=setTimeout(()=>{ if(current===generation){cancel();tell('Simulation stopped after 30 seconds. Try a smaller analysis.');}},30000);
    worker.onmessage=({data})=>{if(!valid()||current!==generation)return; if(data.type==='error'){cancel();tell('Simulation failed: '+data.message);return;} if(data.type==='result'){
      const value=v=>typeof v==='number'?Number(v).toPrecision(6):`${Number(v.real).toPrecision(5)} + ${Number(v.img).toPrecision(5)}i`;
      table.textContent=data.series.map(s=>`${s.name}: ${value(s.values.at(-1))}`).join('\n');plot(data.series);cancel();tell(`Simulation finished: ${data.points} point${data.points===1?'':'s'}${data.points>2000?' (plot sampled)':''}. The table shows the final point.`);
    }};
    worker.onerror=()=>{if(current===generation){cancel();tell('Could not start the simulation worker.');}};worker.postMessage({type:'run',netlist:source.value});
  }
  async function replace(text,expected=revision) { if(dirty&&!await host.ui.confirm('Discard unsaved netlist changes?',{title:'Unsaved changes',confirmLabel:'Discard changes',cancelLabel:'Keep editing',danger:true,signal:host.signal}))return false;if(!valid())return false;if(revision!==expected){tell('The netlist changed while opening. Try again.');return false;}cancel();source.value=text;revision++;documentEpoch++;dirty=true;version=null;savedPath=null;canvas.hidden=true;table.textContent='';return true; }
  async function open() { if(busy||!valid())return;const op=operations.begin('load');if(!op){tell('Another file operation is in progress.');return;}busy=true;const expected=revision;try { const selected=await host.storage.pickFile({extensions:['.cir','.sp','.spice','.txt'],signal:op.signal});if(!selected||!valid()||!op.current())return;const c=await mirrorFileContext(),p=c.path(selected);if(!op.claimDocument('mirror:'+p))throw Error('This file is busy in another window.');const f=typeof c.files.readBounded==='function'?await c.files.readBounded(p,65536,{signal:op.signal}):await c.files.read(p);if(!valid()||!c.valid())return;if(f.status==='conflict')throw Error('Resolve this file conflict in Files first.');const text=new TextDecoder('utf-8',{fatal:true}).decode(f.data);validateNetlist(text);if(!op.current()||!await replace(text,expected)||!c.valid()||!op.current())return;if(!op.setDocument('mirror:'+p))return;savedPath=p;version=f.version;path.value=p;dirty=false;tell('Opened '+p+'.');}catch(e){tell('Could not open circuit: '+e.message);}finally{busy=false;op.finish();} }
  async function save() {
    if(busy||!valid())return;
    const op=operations.begin('save');if(!op){tell('Another file operation is in progress.');return;}busy=true;
    try {
      const netlist=validateNetlist(source.value), target=path.value, previousPath=savedPath,
        previousVersion=version, captured=revision, epoch=documentEpoch, c=await mirrorFileContext(), p=c.path(target);
      if(!op.claimDocument('mirror:'+p))throw Error('This file is busy in another window.');
      if(!/\.(cir|sp|spice|txt)$/i.test(p))throw Error('Choose a .cir, .sp, .spice, or .txt filename.');
      if(!valid()||!c.valid())return;
      let expected=null;
      try {
        const old=await c.files.stat(p);
        if(old.status==='conflict')throw Error('Resolve this file conflict in Files first.');
        if(p===previousPath && previousVersion) {
          if(old.version!==previousVersion)throw Error('The saved circuit changed. Reopen it or save a copy.');
        } else if(!await host.ui.confirm('Replace the existing circuit '+p+'?',{title:'Replace circuit',confirmLabel:'Replace',cancelLabel:'Cancel',danger:true,signal:host.signal})) {
          tell('Circuit save cancelled.');return;
        }
        expected=old.version;
      } catch(e) {
        if(e.message!=='File not found.')throw e;
        if(p===previousPath && previousVersion)throw Error('The saved circuit was removed. Reopen it or save a copy.');
      }
      if(!valid()||!c.valid())return;
      const r=await c.files.write(p,netlist,expected);
      if(!valid()||!c.valid()||!op.current())return;
      if(documentEpoch!==epoch){tell('Saved the earlier circuit; the current circuit remains open.');return;}
      if(!op.setDocument('mirror:'+p))return;
      version=r.version;savedPath=p;
      dirty=revision!==captured||r.status==='conflict';
      tell(r.status==='conflict'?'Saved on this device, but the circuit has conflicting copies. Resolve them in Files.':dirty?'Saved earlier edits; newer edits remain unsaved.':'Saved on this device; syncing with the server.');
    } catch(e){tell('Could not save: '+e.message);} finally{busy=false;op.finish();}
  }
  source.addEventListener('input',()=>{const hadResults=worker||table.textContent;dirty=true;revision++;cancel();canvas.hidden=true;table.textContent='';if(hadResults)tell('Netlist changed. Run the simulation again.');});
  input.addEventListener('change',async()=>{if(busy||!valid()){input.value='';return;}const op=operations.begin('load');if(!op){input.value='';return;}busy=true;const expected=revision;try{const f=input.files?.[0];if(!f)return;if(f.size>65536)throw Error('File exceeds 64 KiB.');const text=await f.text();validateNetlist(text);if(op.current()&&await replace(text,expected)&&op.current()){op.setDocument(null);tell('Imported '+f.name+'. Save it to My files to keep it.');}}catch(e){tell('Could not import circuit: '+e.message);}finally{input.value='';busy=false;op.finish();}});
  async function loadExample(text,message){if(busy||!valid())return;const op=operations.begin('load');if(!op)return;busy=true;try{if(await replace(text)&&op.current()){op.setDocument(null);tell(message);}}finally{busy=false;op.finish();}}
  const openButton=textButton('Open My files',open), saveButton=textButton('Save to My files',save);
  const unbind=[openButton,saveButton,input].map(control=>operations.bindControl(control));
  toolbar.append(textButton('Voltage divider',()=>loadExample(EXAMPLES.divider,'Voltage divider example loaded.')),textButton('RC step',()=>loadExample(EXAMPLES.rc,'RC step example loaded.')),textButton('Basic MOSFET',()=>loadExample(EXAMPLES.mos,'Basic illustrative MOSFET model loaded; this is not a foundry model.')),openButton,textButton('Run',run),textButton('Stop',()=>{cancel();tell('Simulation stopped.');}));
  const savebar=make('div','circuit-toolbar');savebar.append(path,saveButton);
  const note=make('p','circuit-note','Experimental SPICE netlist simulator running on your device. This is a text-based circuit editor, not a graphical schematic editor.');
  const sourceLink=document.createElement('a');sourceLink.href=new URL('./node_modules/codi-ngspice/source-relink.zip',import.meta.url).href;sourceLink.textContent='Source and relinking materials';
  const noticeLink=document.createElement('a');noticeLink.href=new URL('./node_modules/codi-ngspice/NOTICES.txt',import.meta.url).href;noticeLink.textContent='License notices';
  note.append(' ',sourceLink,' · ',noticeLink);
  body.append(toolbar,note,input,source,savebar,status,canvas,table);
  return {element:body,dispose(){disposed=true;for(const release of unbind)release();cancel();}};
}
