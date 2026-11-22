/** @typedef {'queued'|'running'|'ready'|'published'|'failed'} RunStatus */
/** @typedef {'core'|'border'|'noise'|'low_sample'|'no_data'} StationStatus */

/** @param {{status: RunStatus}} run */
export function isProcessing(run) {
  return run.status === 'queued' || run.status === 'running';
}
