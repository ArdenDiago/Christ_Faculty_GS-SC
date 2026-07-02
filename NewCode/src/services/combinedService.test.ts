import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildAuthorIndex } from './combinedService';
import { gscholarAuthors, scopusAuthors } from './authors';

test('buildAuthorIndex: union size matches distinct names across both lists', () => {
  const index = buildAuthorIndex();
  const expectedNames = new Set([...scopusAuthors.map((a) => a.name), ...gscholarAuthors.map((a) => a.name)]);
  assert.equal(index.size, expectedNames.size);
});

test('buildAuthorIndex: Scopus authors come first, in original order, before any GS-only names', () => {
  const index = buildAuthorIndex();
  const names = [...index.keys()];
  const scopusNames = scopusAuthors.map((a) => a.name);
  assert.deepEqual(names.slice(0, scopusNames.length), scopusNames);
});

test('buildAuthorIndex: an author present in both lists has both sides populated', () => {
  const index = buildAuthorIndex();
  const bothSided = scopusAuthors.find((s) => gscholarAuthors.some((g) => g.name === s.name));
  assert.ok(bothSided, 'fixture data should contain at least one author present in both lists');
  const entry = index.get(bothSided!.name);
  assert.ok(entry?.scopus);
  assert.ok(entry?.gscholar);
});

test('buildAuthorIndex: a Scopus-only author has a null gscholar side', () => {
  const index = buildAuthorIndex();
  const scopusOnly = scopusAuthors.find((s) => !gscholarAuthors.some((g) => g.name === s.name));
  if (!scopusOnly) return; // fixture data may not have one; nothing to assert
  const entry = index.get(scopusOnly.name);
  assert.equal(entry?.gscholar, null);
});
