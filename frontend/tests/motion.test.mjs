import test from 'node:test';
import assert from 'node:assert/strict';
import {mountMotion} from '../motion.mjs';

function fixture({reduced = false, supported = true} = {}) {
  const elements = [100, 900, 1100].map(top => ({
    classList: new Set(), style: {setProperty() {}},
    getBoundingClientRect: () => ({top}),
    matches: () => true,
    contains(target) { return target === this || target.parent === this; }
  }));
  const root = new EventTarget();
  root.children = elements;
  root.querySelectorAll = () => elements;
  elements.forEach(element => element.parentElement = root);
  const media = new EventTarget();
  media.matches = reduced;
  let observer;
  class Observer {
    observed = new Set();
    constructor(callback) { this.callback = callback; observer = this; }
    observe(element) { this.observed.add(element); }
    unobserve(element) { this.observed.delete(element); }
    disconnect() { this.observed.clear(); }
    enter(element) { if (this.observed.has(element)) this.callback([{target:element,isIntersecting:true}]); }
  }
  const motion = mountMotion(root, {innerHeight:800, matchMedia:() => media, IntersectionObserver:supported ? Observer : undefined});
  return {root, elements, media, motion, observer};
}

test('initial viewport stays visible and offscreen blocks reveal exactly once', () => {
  const {elements:[visible, first, second], observer, motion} = fixture();
  assert.equal(visible.classList.has('reveal-ready'), false);
  assert.equal(first.classList.has('reveal-ready'), true);
  assert.equal(observer.observed.size, 2);
  observer.enter(first);
  assert.equal(first.classList.has('is-revealed'), true);
  assert.equal(observer.observed.has(first), false);
  observer.enter(first);
  assert.equal(observer.observed.size, 1);
  assert.equal(second.classList.has('is-revealed'), false);
  motion.destroy();
});

test('anchor or keyboard targets reveal their containing block immediately', () => {
  const {elements, observer, motion} = fixture();
  const link = {parent:elements[1],contains:() => false};
  motion.revealWithin(link);
  assert.equal(elements[1].classList.has('is-revealed'), true);
  assert.equal(observer.observed.has(elements[1]), false);
  motion.destroy();
});

test('reduced motion and missing observer leave all content visible', () => {
  for (const options of [{reduced:true},{supported:false}]) {
    const {elements, observer, motion} = fixture(options);
    assert.equal(observer, undefined);
    assert.equal(elements.some(e => e.classList.has('reveal-ready')), false);
    motion.destroy();
  }
});

test('changing motion preference reveals pending content and stops observing', () => {
  const {elements, media, observer, motion} = fixture();
  media.dispatchEvent(Object.assign(new Event('change'), {matches:true}));
  assert.equal(observer.observed.size, 0);
  assert.ok(elements.slice(1).every(e => e.classList.has('is-revealed')));
  motion.destroy();
});

test('route cleanup disconnects observers and makes pending blocks visible', () => {
  const {elements, observer, motion} = fixture();
  motion.destroy();
  motion.destroy();
  assert.equal(observer.observed.size, 0);
  assert.ok(elements.slice(1).every(e => e.classList.has('is-revealed')));
});

test('returning focus to the main landmark preserves offscreen reveal state', () => {
  const {root, elements, observer, motion} = fixture();
  root.dispatchEvent(new Event('focusin'));
  assert.equal(observer.observed.size, 2);
  assert.ok(elements.every(e => !e.classList.has('is-revealed')));
  motion.destroy();
});
