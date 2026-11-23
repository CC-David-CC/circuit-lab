import './style.css';
import { EXAMPLES, validateNetlist } from './netlist.mjs';

const extensions = ['.cir', '.sp', '.spice', '.txt'];
const maxBytes = 64 * 1024;
const revisionPattern = /^[a-f0-9]{64}$/;
const encode = new TextEncoder();
const decode = new TextDecoder('utf-8', {fatal: true});

function circuitPath(value) {
  const path = value.replace(/^(?:webos:)?\//, '');
  const parts = path.split('/');
  if (parts[0] === '.app' || parts.some(part => !part || part === '.' || part === '..' || /[\\\u0000]/.test(part))) {
    throw Error('Choose a valid path in My files.');
  }
  if (!extensions.some(ext => path.toLowerCase().endsWith(ext))) {
    throw Error('Choose a .cir, .sp, .spice, or .txt filename.');
  }
  return path;
}

export function mount(host) {
  const { make, textButton } = host.ui;
  const owner = host.storage.workspaceOwner();
  const session = host.session();
  const abort = new AbortController();
  const signal = AbortSignal.any([abort.signal, host.signal]);
  const body = make('div','window-content circuit-lab'), toolbar = make('div','circuit-toolbar');
  const source = document.createElement('textarea'); source.className = 'circuit-source'; source.spellcheck = false; source.value = EXAMPLES.divider; source.setAttribute('aria-label','SPICE netlist');
  const path = document.createElement('input'); path.value = '/Circuit-' + crypto.randomUUID() + '.cir'; path.setAttribute('aria-label','Circuit file path');
  const status = make('p','circuit-status','Choose an example or open a SPICE netlist.'), table = make('pre','circuit-results'), canvas = document.createElement('canvas');
  status.setAttribute('role', 'status');
  canvas.width = 900; canvas.height = 300; canvas.setAttribute('aria-label','Circuit simulation plot'); canvas.hidden = true;
  const input = document.createElement('input'); input.type = 'file'; input.accept = '.cir,.sp,.spice,.txt'; input.setAttribute('aria-label','Upload circuit file');
  let context, binding = null, releaseWriter, worker = null, timer = null;
  let generation = 0, revision = 0;
  let busy = false, dirty = false, picking = false, transferring = false;
  const valid = () => !signal.aborted && owner === host.storage.workspaceOwner() && session === host.session();
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
    if (!valid() || busy || picking || transferring) return;
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
  function workspace() {
    if (!valid() || !context?.valid()) throw Error('This Files workspace ended.');
    if (transferring) throw Error('Files are being transferred.');
    return context.files;
  }

  function bind(next) {
    workspace();
    if (!binding && !next) return;
    host.desktop.updateAccountFileBinding(host.w, {
      owner, path: next?.path ?? null, sha256: next?.sha256 ?? null,
    });
    binding = next;
  }

  async function confirmDiscard() {
    if (!dirty) return true;
    const expected = revision;
    const allowed = await host.ui.confirm('Discard unsaved netlist changes?', {
      title: 'Unsaved changes', confirmLabel: 'Discard changes', cancelLabel: 'Keep editing', danger: true, signal,
    });
    if (!allowed || !valid()) return false;
    if (expected !== revision) {
      tell('The netlist changed during confirmation. Try again.');
      return false;
    }
    return true;
  }

  async function replace(text, next, expected) {
    if (expected !== revision) {
      tell('The netlist changed while opening. Try again.');
      return false;
    }
    if (!await confirmDiscard()) return false;
    bind(next);
    cancel();
    source.value = text;
    revision++;
    dirty = next == null;
    canvas.hidden = true;
    table.textContent = '';
    return true;
  }

  async function fileTask(errorPrefix, action) {
    if (busy || picking || !valid()) return;
    busy = true;
    try {
      workspace();
      await action();
    } catch (error) {
      tell(errorPrefix + error.message);
    } finally {
      busy = false;
    }
  }

  async function loadFile(target, expected, required) {
    const file = await workspace().read(target, {signal});
    workspace();
    if (!revisionPattern.test(file.sha256) || (required && file.sha256 !== required)) {
      throw Error('The circuit changed in Files.');
    }
    if (file.data.byteLength > maxBytes) throw Error('File exceeds 64 KiB.');
    const text = validateNetlist(decode.decode(file.data));
    if (await replace(text, {path: target, sha256: file.sha256}, expected)) {
      path.value = '/' + target;
      tell('Opened ' + target + '.');
    }
  }

  function open() {
    return fileTask('Could not open circuit. ', async () => {
      const expected = revision;
      const selected = await host.storage.pickWorkspaceFile({extensions, signal});
      if (selected != null) await loadFile(circuitPath(selected), expected);
    });
  }

  function save() {
    return fileTask('Could not save circuit. ', async () => {
      const target = circuitPath(path.value);
      const bytes = encode.encode(validateNetlist(source.value));
      if (bytes.byteLength > maxBytes) throw Error('File exceeds 64 KiB.');
      const captured = revision;
      const expected = binding?.path === target ? binding.sha256 : null;
      let result;
      try {
        result = await workspace().write(target, bytes, expected, {signal});
      } catch (error) {
        if (error.status !== 409) throw error;
        if (expected) throw Error('The saved circuit changed. Reopen it or save a copy.');
        const current = await workspace().version(target, {signal});
        if (!revisionPattern.test(current.sha256)) throw Error('Files did not return a revision.');
        if (!await host.ui.confirm('Replace the existing circuit ' + target + '?', {
          title: 'Replace circuit', confirmLabel: 'Replace', cancelLabel: 'Cancel', danger: true, signal,
        })) {
          tell('Circuit save cancelled.');
          return;
        }
        result = await workspace().write(target, bytes, current.sha256, {signal});
      }
      if (!revisionPattern.test(result.sha256)) throw Error('Files did not confirm the save.');
      bind({path: target, sha256: result.sha256});
      dirty = revision !== captured;
      tell(dirty ? 'Saved earlier edits. Newer edits remain unsaved.' : 'Saved ' + target + '.');
    });
  }

  source.addEventListener('input',()=>{const hadResults=worker||table.textContent;dirty=true;revision++;cancel();canvas.hidden=true;table.textContent='';if(hadResults)tell('Netlist changed. Run the simulation again.');});
  input.addEventListener('click', event => {
    if (picking || busy || !valid() || transferring) {
      event.preventDefault();
      return;
    }
    picking = true;
  });
  input.addEventListener('cancel', () => { picking = false; });
  input.addEventListener('change', async () => {
    picking = false;
    try {
      await fileTask('Could not import circuit. ', async () => {
        const file = input.files?.[0];
        if (!file) return;
        const expected = revision;
        if (file.size > maxBytes) throw Error('File exceeds 64 KiB.');
        const text = validateNetlist(decode.decode(await file.arrayBuffer()));
        if (await replace(text, null, expected)) tell('Imported ' + file.name + '. Save it to My files to keep it.');
      });
    } finally {
      input.value = '';
    }
  });

  function loadExample(text, message) {
    return fileTask('Could not load example. ', async () => {
      if (await replace(text, null, revision)) tell(message);
    });
  }

  const openButton = textButton('Open My files', open);
  const saveButton = textButton('Save to My files', save);
  toolbar.append(textButton('Voltage divider',()=>loadExample(EXAMPLES.divider,'Voltage divider example loaded.')),textButton('RC step',()=>loadExample(EXAMPLES.rc,'RC step example loaded.')),textButton('Basic MOSFET',()=>loadExample(EXAMPLES.mos,'Basic illustrative MOSFET model loaded; this is not a foundry model.')),openButton,textButton('Run',run),textButton('Stop',()=>{cancel();tell('Simulation stopped.');}));
  const savebar=make('div','circuit-toolbar');savebar.append(path,saveButton);
  const note=make('p','circuit-note','Experimental SPICE netlist simulator running on your device. This is a text-based circuit editor, not a graphical schematic editor.');
  const sourceLink=document.createElement('a');sourceLink.href=new URL('./node_modules/codi-ngspice/source-relink.zip',import.meta.url).href;sourceLink.textContent='Source and relinking materials';
  const noticeLink=document.createElement('a');noticeLink.href=new URL('./node_modules/codi-ngspice/NOTICES.txt',import.meta.url).href;noticeLink.textContent='License notices';
  note.append(' ',sourceLink,' · ',noticeLink);
  body.append(toolbar,note,input,source,savebar,status,canvas,table);

  const ready = (async () => {
    context = await host.storage.workspaceFileContext();
    if (context.owner !== owner) throw Error('Circuit Lab belongs to another Files workspace.');
    workspace();
    releaseWriter = context.registerFileWriter?.(async () => {
      if (dirty || busy || picking) throw Error('Finish saving the circuit before transferring Files.');
      transferring = true;
      body.inert = true;
      return () => { body.inert = false; transferring = false; };
    });
    const launch = host.w.launchContext;
    if (launch) {
      if (launch.storage !== 'account' || launch.owner !== owner) throw Error('Open the circuit from My files.');
      await fileTask('Could not restore circuit. ', () => loadFile(
        circuitPath(launch.path), revision, launch.restore ? undefined : launch.sha256,
      ));
    }
  })();
  ready.catch(error => tell(error.message));

  window.addEventListener('beforeunload', event => {
    if (!dirty && !busy && !picking) return;
    event.preventDefault();
    event.returnValue = '';
  }, {signal});

  return {
    element: body,
    ready,
    focus: () => source.focus(),
    async requestClose() {
      if (busy || picking || transferring) {
        tell('Finish the file operation before closing Circuit Lab.');
        return false;
      }
      return confirmDiscard();
    },
    dispose() {
      abort.abort();
      releaseWriter?.();
      cancel();
    },
  };
}
