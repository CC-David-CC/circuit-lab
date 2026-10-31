import { Simulation } from 'eecircuit-engine';
import { validateNetlist } from './netlist.mjs';

// The published engine embeds its WASM as a data URL. Decode that local
// module ourselves: the desktop's connect-src correctly disallows fetching
// data URLs, even though no network request is necessary here.
const nativeFetch = globalThis.fetch;
globalThis.fetch = function(input, options) {
  const url = typeof input === 'string' ? input : input?.url ?? String(input);
  const prefix = 'data:application/wasm;base64,';
  if (url.startsWith(prefix)) {
    const binary = atob(url.slice(prefix.length)), bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return Promise.resolve(new Response(bytes, { headers: { 'Content-Type': 'application/wasm' } }));
  }
  return nativeFetch.call(this, input, options);
};

onmessage = async ({ data }) => {
  if (data?.type !== 'run') return;
  try {
    const netlist = validateNetlist(data.netlist), sim = new Simulation();
    await sim.start(); sim.setNetList(netlist);
    const result = await sim.runSim();
    if (!result || !Array.isArray(result.data) || !Number.isInteger(result.numPoints) || result.numPoints < 1) throw Error(sim.getError().slice(-3).join(' ') || 'The simulator returned no results.');
    const stride = Math.max(1, Math.ceil(result.numPoints / 2000));
    const series = result.data.slice(0, 16).map(s => ({ name: s.name, type: s.type, values: s.values.filter((_, i) => i % stride === 0 || i === s.values.length - 1) }));
    postMessage({ type: 'result', points: result.numPoints, dataType: result.dataType, series, info: sim.getInfo().slice(-4000) });
  } catch (error) { postMessage({ type: 'error', message: String(error?.message || error) }); }
};
