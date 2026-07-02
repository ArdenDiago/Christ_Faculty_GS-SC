import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildPaperId } from './gscholarService';

test('buildPaperId prefers the link when present', () => {
  assert.equal(buildPaperId('https://scholar.google.com/citations?x=1', 'Some Title', '2020'), 'https://scholar.google.com/citations?x=1');
});

test('buildPaperId falls back to title_year when link is N/A', () => {
  assert.equal(buildPaperId('N/A', 'Some Title', '2020'), 'Some Title_2020');
});
