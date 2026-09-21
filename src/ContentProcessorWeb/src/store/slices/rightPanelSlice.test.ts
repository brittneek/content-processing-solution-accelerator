// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/**
 * @file Tests for rightPanelSlice — file blob fetching and response caching.
 */

import reducer, { fetchContentFileData, setSelectedEvidence } from './rightPanelSlice';
import type { RightPanelState } from './rightPanelSlice';

// ── Helpers ────────────────────────────────────────────────────────────

const getInitialState = (): RightPanelState => ({
    fileHeaders: {},
    blobURL: '',
    rLoader: false,
    rError: '',
    fileResponse: [],
    selectedEvidence: null,
});

describe('rightPanelSlice', () => {
    describe('initial state', () => {
        it('should return the correct initial state', () => {
            expect(reducer(undefined, { type: 'unknown' })).toEqual(getInitialState());
        });

        it('stores and clears selected source evidence', () => {
            const selection = {
                entityId: 'maximum_temperature',
                entityName: 'Maximum temperature',
                status: 'fail' as const,
                pageNumber: 2,
                regions: [
                    {
                        page_number: 2,
                        polygon: [
                            { x: 0.1, y: 0.2 },
                            { x: 0.5, y: 0.2 },
                            { x: 0.5, y: 0.3 },
                        ],
                    },
                ],
            };

            const selected = reducer(getInitialState(), setSelectedEvidence(selection));
            expect(selected.selectedEvidence).toEqual(selection);
            expect(reducer(selected, setSelectedEvidence(null)).selectedEvidence).toBeNull();
        });
    });

    // ── fetchContentFileData ─────────────────────────────────────────────

    describe('fetchContentFileData', () => {
        it('should set rLoader and clear blobURL/headers on pending', () => {
            const state = reducer(
                getInitialState(),
                fetchContentFileData.pending('', { processId: 'p-1' })
            );
            expect(state.rLoader).toBe(true);
            expect(state.blobURL).toBe('');
            expect(state.fileHeaders).toEqual({});
            expect(state.rError).toBe('');
        });

        it('should populate fileHeaders and blobURL on fulfilled', () => {
            const payload = {
                headers: { 'content-type': 'application/pdf' },
                blobURL: 'blob:http://localhost/abc',
                processId: 'p-1',
            };
            const state = reducer(
                getInitialState(),
                fetchContentFileData.fulfilled(payload, '', { processId: 'p-1' })
            );
            expect(state.fileHeaders).toEqual(payload.headers);
            expect(state.blobURL).toBe(payload.blobURL);
            expect(state.rLoader).toBe(false);
        });

        it('should cache the response in fileResponse array', () => {
            const payload = {
                headers: { 'content-type': 'image/png' },
                blobURL: 'blob:http://localhost/123',
                processId: 'p-1',
            };
            const state = reducer(
                getInitialState(),
                fetchContentFileData.fulfilled(payload, '', { processId: 'p-1' })
            );
            expect(state.fileResponse).toHaveLength(1);
            expect(state.fileResponse[0].processId).toBe('p-1');
        });

        it('should not duplicate entries in fileResponse for the same processId', () => {
            const initial: RightPanelState = {
                ...getInitialState(),
                fileResponse: [
                    {
                        headers: { 'content-type': 'application/pdf' },
                        blobURL: 'blob:old',
                        processId: 'p-1',
                    },
                ],
            };
            const payload = {
                headers: { 'content-type': 'application/pdf' },
                blobURL: 'blob:new',
                processId: 'p-1',
            };
            const state = reducer(
                initial,
                fetchContentFileData.fulfilled(payload, '', { processId: 'p-1' })
            );
            // Should still have only one entry for p-1
            expect(state.fileResponse).toHaveLength(1);
        });

        it('should add a new entry for a different processId', () => {
            const initial: RightPanelState = {
                ...getInitialState(),
                fileResponse: [
                    { headers: {}, blobURL: 'blob:a', processId: 'p-1' },
                ],
            };
            const payload = {
                headers: { 'content-type': 'text/plain' },
                blobURL: 'blob:b',
                processId: 'p-2',
            };
            const state = reducer(
                initial,
                fetchContentFileData.fulfilled(payload, '', { processId: 'p-2' })
            );
            expect(state.fileResponse).toHaveLength(2);
        });

        it('should set rError on rejected', () => {
            const state = reducer(
                getInitialState(),
                fetchContentFileData.rejected(
                    new Error('Network failure'),
                    '',
                    { processId: 'p-1' }
                )
            );
            expect(state.rLoader).toBe(false);
            expect(state.rError).toBe('Network failure');
        });

        it('should set a default error message when none is provided', () => {
            const state = reducer(
                getInitialState(),
                fetchContentFileData.rejected(
                    new Error(),
                    '',
                    { processId: 'p-1' }
                )
            );
            expect(state.rError).toBe('An error occurred');
        });
    });
});
