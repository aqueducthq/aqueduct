import { IconDefinition } from '@fortawesome/fontawesome-svg-core';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import React from 'react';
import { Handle, Position } from 'react-flow-renderer';
import { useSelector } from 'react-redux';

import { RootState } from '../../../stores/store';
import { theme } from '../../../styles/theme/theme';
import { ArtifactType } from '../../../utils/artifacts';
import { ReactFlowNodeData, ReactflowNodeType } from '../../../utils/reactflow';
import ExecutionStatus, { CheckStatus } from '../../../utils/shared';
import { BaseNode } from './BaseNode.styles';
import {CheckLevel} from "../../../utils/operators";

type Props = {
  data: ReactFlowNodeData;
  defaultLabel: string;
  isConnectable: boolean;
  icon: IconDefinition;
};

export const Node: React.FC<Props> = ({
  data,
  defaultLabel,
  isConnectable,
  icon,
}) => {
  const label = data.label ? data.label : defaultLabel;
  const currentNode = useSelector(
    (state: RootState) => state.nodeSelectionReducer.selected
  );
  const workflowState = useSelector(
    (state: RootState) => state.workflowReducer
  );
  const selected = currentNode.id === data.nodeId;

  let status: CheckStatus | ExecutionStatus;
  if (data.nodeType === ReactflowNodeType.Operator) {
    status = workflowState.operatorResults[data.nodeId]?.result?.status;
  } else {
    const artifactResult = workflowState.artifactResults[data.nodeId];
    if (
      workflowState.selectedDag.artifacts[data.nodeId]?.spec.type ===
      ArtifactType.Bool
    ) {
      status = artifactResult?.result?.data as CheckStatus;
    } else {
      status = artifactResult?.result?.status;
    }
  }

  function getOpIDFromArtifactID(artifact_id: string): string {
    for (const opID in workflowState.selectedDag.operators) {
      const op = workflowState.selectedDag.operators[opID]
      if (op.inputs.indexOf(artifact_id) >= 0) {
        return op.id;
      }
    }
    return "";
  }

  let borderColor, backgroundColor, hoverColor, textColor;
  switch (status) {
    case CheckStatus.Succeeded:
    case ExecutionStatus.Succeeded:
      borderColor = 'green.600';
      backgroundColor = selected ? 'green.200' : 'green.25';
      hoverColor = 'green.100';
      textColor = 'green.800';
      break;
    case CheckStatus.Failed:
      // We use yellow to denote a check warning.
      const checkOpID = getOpIDFromArtifactID(data.nodeId);
      if (workflowState.selectedDag.operators[checkOpID].spec.check?.level == CheckLevel.Warning) {
        borderColor = 'yellow.400';
        backgroundColor = selected ? 'yellow.200' : 'yellow.25';
        hoverColor = 'yellow.100';
        textColor = 'yellow.800';
        break;
      }
      // A failed check with error severity should fallthrough.
    case ExecutionStatus.Failed:
      borderColor = 'red.500';
      backgroundColor = selected ? 'red.300' : 'red.25';
      hoverColor = 'red.100';
      textColor = 'red.800';
      break;
    default:
      borderColor = 'gray.600';
      backgroundColor = selected ? 'gray.300' : 'gray.100';
      hoverColor = 'gray.200';
      textColor = 'black';
      break;
  }

  return (
    <BaseNode
      sx={{
        backgroundColor,
        color: textColor,
        borderColor: borderColor,
        '&:hover': { backgroundColor: hoverColor },
      }}
    >
      <Box sx={{ fontSize: '50px', mb: '2px' }}>
        <FontAwesomeIcon icon={icon} />
      </Box>
      <Typography
        sx={{
          fontSize: '18px',
          maxWidth: '200px',
          overflow: 'clip',
          textOverflow: 'wrap',
          overflowWrap: 'normal',
          textAlign: 'center',
        }}
      >
        {label}
      </Typography>

      <Handle
        type="source"
        id="db-source-id"
        style={{
          background: theme.palette.darkGray as string,
          border: theme.palette.darkGray as string,
        }}
        isConnectable={isConnectable}
        position={Position.Right}
      />
      <Handle
        type="target"
        id="db-target-id"
        style={{
          background: theme.palette.darkGray as string,
          border: theme.palette.darkGray as string,
        }}
        isConnectable={isConnectable}
        position={Position.Left}
      />
    </BaseNode>
  );
};

export default Node;
