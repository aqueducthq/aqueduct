import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import React, { useState } from 'react';
import { useSelector } from 'react-redux';

import { OperatorsForIntegrationItem } from '../../reducers/integrationOperators';
import { RootState } from '../../stores/store';
import { isFailed, isLoading } from '../../utils/shared';
import { ListWorkflowSummary } from '../../utils/workflows';
import WorkflowAccordion from '../workflows/accordion';

const OperatorsOnIntegration: React.FC = () => {
  const listWorkflowState = useSelector(
    (state: RootState) => state.listWorkflowReducer
  );
  const operatorsState = useSelector((state: RootState) => {
    return state.integrationOperatorsReducer;
  });
  const [expandedWf, setExpandedWf] = useState<string>('');

  if (
    isLoading(operatorsState.loadingStatus) ||
    isLoading(listWorkflowState.loadingStatus)
  ) {
    return <CircularProgress />;
  }

  if (
    isFailed(operatorsState.loadingStatus) ||
    isFailed(listWorkflowState.loadingStatus)
  ) {
    return (
      <Alert severity="error">
        <AlertTitle>
          {
            "We couldn't retrieve workflows associated with this integration for now."
          }
        </AlertTitle>
      </Alert>
    );
  }

  const workflows = listWorkflowState.workflows;
  const operators = operatorsState.operators;

  const workflowMap: { [id: string]: ListWorkflowSummary } = {};
  workflows.map((wf) => {
    workflowMap[wf.id] = wf;
  });
  const operatorsByWorkflow: {
    [id: string]: {
      workflow?: ListWorkflowSummary;
      operators: OperatorsForIntegrationItem[];
    };
  } = {};

  operators.map((op) => {
    const wf = workflowMap[op.workflow_id];
    if (!operatorsByWorkflow[op.workflow_id]) {
      operatorsByWorkflow[op.workflow_id] = { workflow: wf, operators: [] };
    }
    operatorsByWorkflow[op.workflow_id].operators.push(op);
  });

  return (
    <Box>
      {Object.entries(operatorsByWorkflow).map(([wfId, item]) => (
        <WorkflowAccordion
          expanded={expandedWf === wfId}
          handleExpand={() => {
            if (expandedWf === wfId) {
              setExpandedWf('');
              return;
            }
            setExpandedWf(wfId);
          }}
          key={wfId}
          workflow={item.workflow}
          operators={item.operators}
        />
      ))}
    </Box>
  );
};

export default OperatorsOnIntegration;
