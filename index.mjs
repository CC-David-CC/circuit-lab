import './style.css';
import { EXAMPLES, validateNetlist } from './netlist.mjs';

export function mount(host) {
  const { make, textButton } = host.ui, { mirrorFileContext, signedInSubject } = host.storage;
  const owner = signedInSubject(), body = make('div','window-content circuit-lab'), toolbar = make('div','circuit-toolbar');
  const source = document.createElement('textarea'); source.className = 'circuit-source'; source.spellcheck = false; source.value = EXAMPLES.divider; source.setAttribute('aria-label','SPICE netlist');
  const path = document.createElement('input'); path.value = '/Circuit-' + crypto.randomUUID() + '.cir'; path.setAttribute('aria-label','Circuit file path');
  const status = make('p','circuit-status','Choose an example or open a SPICE netlist.'), table = make('pre','circuit-results'), canvas = document.createElement('canvas');
  canvas.width = 900; canvas.height = 300; canvas.setAttribute('aria-label','Circuit simulation plot'); canvas.hidden = true;
  const input = document.createElement('input'); input.type = 'file'; input.accept = '.cir,.sp,.spice,.txt'; input.setAttribute('aria-label','Upload circuit file');
  let disposed = false, worker = null, generation = 0, timer = null, version = null, savedPath = null, dirty = false, busy = false;
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
  function replace(text) { if(dirty&&!confirm('Discard unsaved netlist changes?'))return false;source.value=text;dirty=true;version=null;savedPath=null;canvas.hidden=true;table.textContent='';return true; }
  async function open() { try { const p=await host.storage.pickFile({extensions:['.cir','.sp','.spice','.txt'],signal:host.signal});if(!p||!valid())return;const c=await mirrorFileContext(),f=await c.files.read(p);if(!valid()||!c.valid())return;if(f.status==='conflict')throw Error('Resolve this file conflict in Files first.');const text=new TextDecoder('utf-8',{fatal:true}).decode(f.data);validateNetlist(text);if(!replace(text))return;savedPath=p;version=f.version;path.value=p;dirty=false;tell('Opened '+p+'.');}catch(e){tell('Could not open circuit: '+e.message);} }
  async function save() { if(busy)return;busy=true;try{const netlist=validateNetlist(source.value),c=await mirrorFileContext(),p=c.path(path.value);if(!/\.(cir|sp|spice|txt)$/i.test(p))throw Error('Choose a .cir, .sp, .spice, or .txt filename.');const r=await c.files.write(p,netlist,p===savedPath?version:null);if(!valid()||!c.valid())return;version=r.version;savedPath=p;dirty=source.value!==netlist;tell(dirty?'Saved earlier edits; newer edits remain unsaved.':'Saved on this device; syncing with the server.');}catch(e){tell('Could not save: '+e.message);}finally{busy=false;} }
  source.addEventListener('input',()=>{dirty=true;});
  input.addEventListener('change',async()=>{try{const f=input.files?.[0];if(!f)return;if(f.size>65536)throw Error('File exceeds 64 KiB.');const text=await f.text();validateNetlist(text);if(replace(text))tell('Imported '+f.name+'. Save it to My files to keep it.');}catch(e){tell('Could not import circuit: '+e.message);}finally{input.value='';}});
  toolbar.append(textButton('Voltage divider',()=>{if(replace(EXAMPLES.divider))tell('Voltage divider example loaded.');}),textButton('RC step',()=>{if(replace(EXAMPLES.rc))tell('RC step example loaded.');}),textButton('Basic MOSFET',()=>{if(replace(EXAMPLES.mos))tell('Basic illustrative MOSFET model loaded; this is not a foundry model.');}),textButton('Open My files',open),textButton('Run',run),textButton('Stop',()=>{cancel();tell('Simulation stopped.');}));
  const savebar=make('div','circuit-toolbar');savebar.append(path,textButton('Save to My files',save));
  const note=make('p','circuit-note','Experimental SPICE netlist simulator running on your device. This is a text-based circuit editor, not a graphical schematic editor.');
  const sourceLink=document.createElement('a');sourceLink.href=new URL('./node_modules/codi-ngspice/source-relink.zip',import.meta.url).href;sourceLink.textContent='Source and relinking materials';
  const noticeLink=document.createElement('a');noticeLink.href=new URL('./node_modules/codi-ngspice/NOTICES.txt',import.meta.url).href;noticeLink.textContent='License notices';
  note.append(' ',sourceLink,' · ',noticeLink);
  body.append(toolbar,note,input,source,savebar,status,canvas,table);
  return {element:body,dispose(){disposed=true;cancel();}};
}
