import { useAqueductConsts } from '@aqueducthq/common/src/components/hooks/useAqueductConsts';
import { DataPreview } from '@aqueducthq/common/src/utils/data';
import { LoadingStatus, LoadingStatusEnum } from '@aqueducthq/common/src/utils/shared';
import { createAsyncThunk, createSlice, PayloadAction } from '@reduxjs/toolkit';

const { apiAddress, httpProtocol } = useAqueductConsts();

export interface DataPreviewState {
    loadingStatus: LoadingStatus;
    data: DataPreview;
}

const initialPreviewState: DataPreviewState = {
    loadingStatus: { loading: LoadingStatusEnum.Initial, err: '' },
    data: {
        historical_versions: {},
        latest_versions: {},
    },
};

export const getDataArtifactPreview = createAsyncThunk<DataPreview, { apiKey: string }>(
    'dataPreviewReducer/fetch',
    async (
        args: {
            apiKey: string;
        },
        thunkAPI,
    ) => {
        const { apiKey } = args;
        const response = await fetch(`${httpProtocol}://${apiAddress}/artifact_versions`, {
            method: 'GET',
            headers: {
                'api-key': apiKey,
            },
        });

        const body = await response.json();

        if (!response.ok) {
            return thunkAPI.rejectWithValue(body.error);
        }

        return body as DataPreview;
    },
);

export const dataPreviewSlice = createSlice({
    name: 'dataPreviewReducer',
    initialState: initialPreviewState,
    reducers: {},
    extraReducers: (builder) => {
        builder.addCase(getDataArtifactPreview.pending, (state) => {
            state.loadingStatus = { loading: LoadingStatusEnum.Loading, err: '' };
        });

        builder.addCase(getDataArtifactPreview.fulfilled, (state, { payload }: PayloadAction<DataPreview>) => {
            state.loadingStatus = { loading: LoadingStatusEnum.Succeeded, err: '' };
            state.data = payload;
        });

        builder.addCase(getDataArtifactPreview.rejected, (state, { payload }) => {
            state.loadingStatus = {
                loading: LoadingStatusEnum.Failed,
                err: payload as string,
            };
        });
    },
});

export default dataPreviewSlice.reducer;
