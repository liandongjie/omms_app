import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CONNECTED_RECONCILIATION_INTERVAL_MS,
  FALLBACK_POLL_INTERVAL_MS,
  createRefreshCoordinator,
  getAutoRefreshInterval,
} from '../src/utils/refreshCoordinator.ts';

test('polling uses low-frequency reconciliation online and fallback offline', () => {
  assert.equal(getAutoRefreshInterval(true, true, true), CONNECTED_RECONCILIATION_INTERVAL_MS);
  assert.equal(getAutoRefreshInterval(true, false, true), FALLBACK_POLL_INTERVAL_MS);
  assert.equal(getAutoRefreshInterval(false, true, true), undefined);
  assert.equal(getAutoRefreshInterval(true, false, false), undefined);
});

test('manual mode ignores automatic refresh requests', async () => {
  let calls = 0;
  const coordinator = createRefreshCoordinator(async () => {
    calls += 1;
  });

  await coordinator.requestAutomatic(false);

  assert.equal(calls, 0);
});

test('events during refresh coalesce into one serial follow-up', async () => {
  let calls = 0;
  let active = 0;
  let maxActive = 0;
  let releaseFirst!: () => void;
  const firstBlocked = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  const coordinator = createRefreshCoordinator(async () => {
    calls += 1;
    active += 1;
    maxActive = Math.max(maxActive, active);
    if (calls === 1) await firstBlocked;
    active -= 1;
  });

  const first = coordinator.request();
  await Promise.resolve();
  await Promise.all([coordinator.request(), coordinator.request(), coordinator.request()]);
  releaseFirst();
  await first;

  assert.equal(calls, 2);
  assert.equal(maxActive, 1);
});

test('manual switch can cancel an automatic pending refresh', async () => {
  let calls = 0;
  let releaseFirst!: () => void;
  const firstBlocked = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  const coordinator = createRefreshCoordinator(async () => {
    calls += 1;
    if (calls === 1) await firstBlocked;
  });

  const first = coordinator.requestAutomatic(true);
  await Promise.resolve();
  await coordinator.requestAutomatic(true);
  coordinator.cancelPending();
  releaseFirst();
  await first;

  assert.equal(calls, 1);
});
