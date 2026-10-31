export const EXAMPLES = {
  divider: `Voltage divider\nV1 in 0 DC 10\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n`,
  rc: `RC step response\nV1 in 0 PULSE(0 5 0 1n 1n 10m 20m)\nR1 in out 1k\nC1 out 0 1u\n.tran 20u 5m\n.end\n`,
};

// Keep initial experiments self-contained: ngspice's interactive command and
// filesystem directives are intentionally outside this app's interface.
export function validateNetlist(text) {
  if (typeof text !== 'string' || !text.trim() || text.length > 65536) throw Error('Enter a netlist of at most 64 KiB.');
  const lines = text.replaceAll('\r','').split('\n');
  if (lines.length < 3 || !lines[0].trim()) throw Error('The first line must be a circuit title.');
  let analysis = 0, end = false;
  for (const line of lines.slice(1)) {
    const content = line.trim();
    if (!content || content.startsWith('*')) continue;
    if (content.includes(';') || content.includes('`')) throw Error('Inline commands are not supported.');
    if (content.startsWith('.')) {
      const directive = content.split(/\s+/)[0].toLowerCase();
      if (!['.op','.tran','.ac','.dc','.model','.end'].includes(directive)) throw Error(`Directive ${directive} is not supported in this preview.`);
      if (['.op','.tran','.ac','.dc'].includes(directive)) analysis++;
      if (directive === '.end') end = true;
    }
  }
  if (analysis !== 1 || !end) throw Error('Include one analysis (.op, .tran, .ac, or .dc) and .end.');
  return text;
}
