import { Alert, Snackbar, Typography } from '@mui/material';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

import * as style from '../../styles/markdown.module.css';
import { getPathPrefix } from '../../utils/getPathPrefix';
import { ListWorkflowSummary } from '../../utils/workflows';
import { Card } from '../layouts/card';
import WorkflowStatus from './workflowStatus';

type Props = {
  workflow: ListWorkflowSummary;
};

const WorkflowCard: React.FC<Props> = ({ workflow }) => {
  const toastMessage = `This workflow has not been run yet. You can inspect it once it's been run.`;
  const [showInfoToast, setShowInfoToast] = useState(false);
  const handleInfoToastClose = () => {
    setShowInfoToast(false);
  };

  const lastUpdatedTime = new Date(workflow['last_run_at'] * 1000);

  const lastRunComponent = (
    <Box sx={{ fontSize: 1, my: 1 }}>
      <Typography variant="subtitle1">
        <strong>Workflow Last Run:</strong> {lastUpdatedTime.toLocaleString()}
      </Typography>
    </Box>
  );

  const cardContent = (
    <Card>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Box sx={{ flex: 1 }}>
          <Typography
            variant="h4"
            gutterBottom
            component="div"
            sx={{
              fontFamily: 'Monospace',
              '&:hover': { textDecoration: 'underline' },
            }}
          >
            {workflow.name}
          </Typography>
        </Box>
        <WorkflowStatus status={workflow.status} />
      </Box>

      <Box sx={{ flex: '1' }}>
        {lastRunComponent}

        {workflow.description && (
          <Box my={1}>
            <Box
              sx={{
                maxHeight: '80px',
                overflowY: 'hidden',
                textOverflow: 'ellipsis',
                mt: 1,
              }}
            >
              <ReactMarkdown className={style.reactMarkdown}>
                {workflow.description}
              </ReactMarkdown>
            </Box>
          </Box>
        )}
      </Box>
    </Card>
  );

  // Only make this a link to the workflow page if the workflow has already
  // been run.
  if (workflow['last_run_at']) {
    return (
      <Link
        underline="none"
        color="inherit"
        href={`${getPathPrefix()}/workflow/${workflow.id}`}
      >
        {cardContent}
      </Link>
    );
  } else {
    return (
      <Box onClick={() => setShowInfoToast(true)}>
        {cardContent}
        <Snackbar
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          open={showInfoToast}
          onClose={handleInfoToastClose}
          key={'workflowCard-success-snackbar'}
          autoHideDuration={6000}
        >
          <Alert
            onClose={handleInfoToastClose}
            severity="success"
            sx={{ width: '100%' }}
          >
            {toastMessage}
          </Alert>
        </Snackbar>
      </Box>
    );
  }
};

export default WorkflowCard;
