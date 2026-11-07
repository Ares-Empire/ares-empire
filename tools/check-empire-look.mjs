// Offline check of the shipped hub links; no browser or network required.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../web/app/empire-api.js', import.meta.url), 'utf8');
const sample = JSON.parse(readFileSync(new URL('../web/app/samples/empire.demo.json', import.meta.url), 'utf8'));
function hub(path) {
  const bands = [];
  const context = vm.createContext({
    URL, URLSearchParams, location: new URL(path, 'https://www.ares-empire.de'), window: {},
    document: {
      documentElement: {classList: {add: (name) => assert.equal(name, 'demo')}},
      createElement: () => ({}), body: {appendChild: (node) => bands.push(node)}
    }
  });
  vm.runInContext(source, context);
  return {api: context.window.EmpireData, bands};
}

const {api: demo, bands} = hub('/demo');
for (const [slug, expected] of [
  ['aresium', 'https://aresium.de/demo?look=dark'],
  ['arestemis', 'https://arestemis.de/?look=dark'],
  ['arestoteles', 'https://www.ares-empire.de/contact?look=dark']
]) {
  assert.equal(demo.destination(sample.projects.find((province) => province.slug === slug)), expected);
}
assert.equal(bands.length, 1);
assert.ok(bands[0].innerHTML.includes('href="https://www.ares-empire.de/contact?topic=access&look=dark"'));
const {api} = hub('/');
assert.equal(api.destination({slug: 'arestemis', state: 'open', url: 'https://arestemis.de/'}),
  'https://arestemis.de/?look=dark');
assert.equal(api.destination({slug: 'aresium', state: 'open', url: 'https://aresium.de/'}), '/sso?to=aresium');
assert.equal(api.destination({slug: 'arestoteles', state: 'open', url: 'https://arestoteles.de/'}),
  'https://arestoteles.de/');
assert.equal(api.destination({slug: 'arestemis', state: 'open', url: 'https://arestemis.de/?lang=de&look=light#hunts'}),
  'https://arestemis.de/?lang=de&look=dark#hunts');
assert.equal(api.destination({slug: 'arestemis', state: 'coming-soon', url: 'https://arestemis.de/'}), null);
assert.equal(api.destination({slug: 'aresync', state: 'open', url: null}), null);

for (const path of ['/contact', '/kontakt', '/arestemis/contact', '/arestemis/kontakt']) {
  for (const prefix of ['', 'https://www.ares-empire.de']) {
    assert.equal(api.passLook(`${prefix}${path}?topic=access#form`), `${prefix}${path}?topic=access&look=dark#form`);
  }
}
for (const path of ['/', '/demo', '/contact', '/kontakt', '/anything']) {
  assert.equal(api.passLook(`https://aresium.de${path}`), `https://aresium.de${path}?look=dark`);
}
for (const path of ['/contact', '/kontakt']) {
  assert.equal(api.passLook(`https://arestemis.de${path}`), `https://arestemis.de${path}?look=dark`);
}
for (const href of ['/sso?to=aresium', '/login', 'https://arestoteles.de/?q=demo#top',
  'https://other.example/contact', 'https://constructor/contact', 'https://arestemis.de/other', 'https://www.ares-empire.de/demo',
  'mailto:hello@example.org', 'arestemis://', 'https://[invalid', null, '']) {
  assert.equal(api.passLook(href), href);
}
assert.equal(api.passLook('https://testflight.apple.com/join/example'), 'https://testflight.apple.com/join/example');
console.log('Hub look: demo destinations, hand-off, contact links, query/fragment and unchanged URLs passed.');
