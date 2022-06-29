import React from 'react';
import { Node } from 'react-flow-renderer';

import DataPreviewSideSheet from '../components/workflows/SideSheets/DataPreviewSideSheet';
import OperatorResultsSideSheet from '../components/workflows/SideSheets/OperatorResultsSideSheet';
import { NodeType, SelectedNode, selectNode } from '../reducers/nodeSelection';
import {
  setBottomSideSheetOpenState,
  setRightSideSheetOpenState,
} from '../reducers/openSideSheet';
import { AppDispatch } from '../stores/store';
import UserProfile from './auth';
import { ReactFlowNodeData } from './reactflow';

/**
 * This function takes in a dispatch call (which must be created in a
 * component) and a call to a set state function in the using component, and it
 * returns a function which takes an event for a click on a node in ReactFlow
 * and opens the appropriate corresponding sidesheet.
 */
export const sideSheetSwitcher = (dispatch: AppDispatch) => {
  return (event: React.MouseEvent, element: Node<ReactFlowNodeData>): void => {
    dispatch(selectNode({ id: element.id, type: element.type as NodeType }));
    dispatch(setRightSideSheetOpenState(true));
    dispatch(setBottomSideSheetOpenState(true));
  };
};

export function getDataSideSheetContent(
  user: UserProfile,
  currentNode: SelectedNode
): React.ReactElement {
  switch (currentNode.type) {
    case NodeType.BoolArtifact:
    case NodeType.FloatArtifact:
    case NodeType.TableArtifact:
    case NodeType.JsonArtifact:
      return <DataPreviewSideSheet artifactId={currentNode.id} />;
    case NodeType.CheckOp:
    case NodeType.MetricOp:
    case NodeType.ExtractOp:
    case NodeType.LoadOp:
    case NodeType.FunctionOp:
      return <OperatorResultsSideSheet user={user} currentNode={currentNode} />;
  }
}
