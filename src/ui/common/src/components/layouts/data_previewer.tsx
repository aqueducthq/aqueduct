import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import React from 'react';

import { ArtifactResult } from '../../reducers/workflow';
import { ExecutionStatus, LoadingStatusEnum } from '../../utils/shared';
import DataTable from '../tables/data_table';
import LogBlock, { LogLevel } from '../text/LogBlock';

type Props = {
  previewData: ArtifactResult;
  error?: string;
};

const DataPreviewer: React.FC<Props> = ({ previewData, error }) => {
  if (!previewData) {
    return null;
  }

  let errorMessage: React.ReactElement;
  if (error) {
    errorMessage = (
      <LogBlock
        logText={error.trim()}
        level={LogLevel.Error}
        title="An error occurred during execution"
      />
    );
  } else if (previewData.result?.status === ExecutionStatus.Failed) {
    // If the execution status is marked as failed but there is no error,
    // that means something upstream from where we are failed.
    errorMessage = (
      <Alert severity="warning">
        <AlertTitle>
          {' '}
          An upstream operator failed, ending the workflow execution.{' '}
        </AlertTitle>
      </Alert>
    );
  }

  const loadingStatus = previewData.loadingStatus;

  if (loadingStatus && loadingStatus.loading === LoadingStatusEnum.Loading) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (loadingStatus && loadingStatus.loading === LoadingStatusEnum.Failed) {
    errorMessage = (
      <Box>
        <Alert severity="error">
          <Typography sx={{ fontFamily: 'Monospace', whiteSpace: 'pre-wrap' }}>
            {loadingStatus.err}
          </Typography>
        </Alert>
      </Box>
    );
  }

  let data: React.ReactElement;
  if (previewData.result && previewData.result.data) {
    if (previewData.result.schema.length > 0) {
      const parsedData = JSON.parse(previewData.result.data);
      data = <DataTable data={parsedData} />;
    } else {
      data = (
        <Typography sx={{ fontFamily: 'Monospace', whiteSpace: 'pre-wrap' }}>
          {previewData.result.data}
        </Typography>
      );
    }
  }

  return (
    <>
      {errorMessage}
      {data}
    </>
  );
};

export default DataPreviewer;
