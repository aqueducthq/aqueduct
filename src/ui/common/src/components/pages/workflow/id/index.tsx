import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import { parse } from 'query-string';
import React, { useEffect, useState } from 'react';
import { ReactFlowProvider } from 'react-flow-renderer';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams } from 'react-router-dom';

import { handleLoadIntegrations } from '../../../../reducers/integrations';
import {
  NodeType,
  resetSelectedNode,
} from '../../../../reducers/nodeSelection';
import {
  setAllSideSheetState,
  setBottomSideSheetOpenState,
} from '../../../../reducers/openSideSheet';
import {
  handleGetArtifactResults,
  handleGetOperatorResults,
  handleGetWorkflow,
  selectResultIdx,
} from '../../../../reducers/workflow';
import { AppDispatch, RootState } from '../../../../stores/store';
import { Artifact } from '../../../../utils/artifacts';
import UserProfile from '../../../../utils/auth';
import { Data } from '../../../../utils/data';
import { Operator } from '../../../../utils/operators';
import { exportCsv } from '../../../../utils/preview';
import { getDagLayoutElements } from '../../../../utils/reactflow';
import { LoadingStatusEnum } from '../../../../utils/shared';
import {
  getDataSideSheetContent,
  sideSheetSwitcher,
} from '../../../../utils/sidesheets';
import DefaultLayout, { MenuSidebarOffset } from '../../../layouts/default';
import {
  AqueductSidebar,
  BottomSidebarHeaderHeightInPx,
  BottomSidebarHeightInPx,
  getBottomSideSheetWidth,
  SidebarPosition,
} from '../../../layouts/sidebar/AqueductSidebar';
import { Button } from '../../../primitives/Button.styles';
import ReactFlowCanvas from '../../../workflows/ReactFlowCanvas';
import WorkflowStatusBar from '../../../workflows/StatusBar';
import WorkflowHeader from '../../../workflows/workflowHeader';

type WorkflowPageProps = {
  user: UserProfile;
};

const WorkflowPage: React.FC<WorkflowPageProps> = ({ user }) => {
  const navigate = useNavigate();
  const dispatch: AppDispatch = useDispatch();
  const workflowId = useParams().id;

  const currentNode = useSelector(
    (state: RootState) => state.nodeSelectionReducer.selected
  );
  const workflow = useSelector((state: RootState) => state.workflowReducer);
  const [dagLayoutElements, setDagLayoutElements] = useState({
    nodes: [],
    edges: [],
  });
  const switchSideSheet = sideSheetSwitcher(dispatch);
  const openSideSheetState = useSelector(
    (state: RootState) => state.openSideSheetReducer
  );
  const artifactResult = useSelector(
    (state: RootState) => state.workflowReducer.artifactResults[currentNode.id]
  );

  useEffect(() => {
    if (workflow.selectedDag !== undefined) {
      document.title = `${workflow.selectedDag.metadata.name} | Aqueduct`;
    }
  }, [workflow.selectedDag]);

  useEffect(() => {
    const urlSearchParams = parse(window.location.search);
    if (
      workflow.selectedResult !== undefined &&
      !urlSearchParams.workflowDagResultId
    ) {
      navigate(`?workflowDagResultId=${encodeURI(workflow.selectedResult.id)}`);
    }
  }, [workflow.selectedResult]);

  useEffect(() => {
    dispatch(handleGetWorkflow({ apiKey: user.apiKey, workflowId }));
    dispatch(handleLoadIntegrations({ apiKey: user.apiKey }));
  }, []);

  useEffect(() => {
    if (workflow.dagResults && workflow.dagResults.length > 0) {
      let workflowDagResultIndex = 0;
      const { workflowDagResultId } = parse(window.location.search);
      for (let i = 0; i < workflow.dagResults.length; i++) {
        if (workflow.dagResults[i].id === workflowDagResultId) {
          workflowDagResultIndex = i;
        }
      }
      if (workflowDagResultId !== workflow.selectedResult.id) {
        dispatch(setAllSideSheetState(false));
        dispatch(selectResultIdx(workflowDagResultIndex));
      }
    }
  }, [workflow.dagResults, window.location.search]);

  /**
   * This function dispatches calls to fetch artifact results and contents.
   *
   * This function is only activated when another similar fetch request
   * hasn't already been triggered.
   *
   * @param nodeId the UUID of the artifact for which we're retrieving
   * details.
   */
  const updateArtifactDetails = (nodeId: string) => {
    const artf = (workflow.selectedDag?.artifacts ?? {})[nodeId];
    if (!artf || !workflow.selectedResult) {
      return;
    }

    if (!(nodeId in workflow.artifactResults)) {
      dispatch(
        handleGetArtifactResults({
          apiKey: user.apiKey,
          workflowDagResultId: workflow.selectedResult.id,
          artifactId: nodeId,
        })
      );
    }
  };

  /**
   * This function fetches both the metadata of a particular operator as well
   * as the results of the artifacts that were both inputs and outputs for
   * this operator.
   *
   * This function is only activated when another similar fetch request
   * hasn't already been triggered.
   *
   * @param nodeId the UUID of an artifact for which we're retrieving
   * results.
   */
  const updateOperatorDetails = (nodeId: string) => {
    // Verify the node is indeed an operator, and a result is selected
    const op = (workflow.selectedDag?.operators ?? {})[nodeId];
    if (!op || !workflow.selectedResult) {
      return;
    }

    if (!(nodeId in workflow.operatorResults)) {
      dispatch(
        handleGetOperatorResults({
          apiKey: user.apiKey,
          workflowDagResultId: workflow.selectedResult.id,
          operatorId: nodeId,
        })
      );
    }

    for (const artfId of [...op.inputs, ...op.outputs]) {
      updateArtifactDetails(artfId);
    }
  };

  useEffect(() => {
    updateOperatorDetails(currentNode.id);
    updateArtifactDetails(currentNode.id);
  }, [currentNode.id, workflow.selectedResult?.id]);

  const selectedDag = workflow.selectedDag;
  const onChange = () => {
    setDagLayoutElements((els) => {
      return els;
    });
  };

  const onPaneClicked = (event: React.MouseEvent) => {
    event.preventDefault();
    dispatch(setBottomSideSheetOpenState(false));

    // Reset selected node
    dispatch(resetSelectedNode());
  };

  const asyncSetDagLayoutElements = async (
    operators: { [id: string]: Operator },
    artifacts: { [id: string]: Artifact },
    apiKey: string
  ) => {
    const elem = await getDagLayoutElements(
      operators,
      artifacts,
      onChange,
      () => {
        // Do nothing.
      },
      apiKey
    );

    setDagLayoutElements(elem);
  };

  const updateLayout = () => {
    if (
      workflow.loadingStatus.loading === LoadingStatusEnum.Succeeded &&
      !!selectedDag
    ) {
      asyncSetDagLayoutElements(
        selectedDag.operators,
        selectedDag.artifacts,
        user.apiKey
      );
    }
  };

  const getDagDetails = () => {
    if (
      workflow.loadingStatus.loading === LoadingStatusEnum.Succeeded &&
      !!selectedDag
    ) {
      for (const op of Object.values(selectedDag.operators)) {
        // We don't need to call updateArtifactDetails because
        // updateOperatorDetails automatically does that for us.
        updateOperatorDetails(op.id);
      }
    }
  };

  useEffect(getDagDetails, [workflow.selectedDag]);

  useEffect(updateLayout, [
    user.apiKey,
    workflow.selectedDag,
    workflow.selectedResult,
    workflow.loadingStatus.loading,
    openSideSheetState.bottomSideSheetOpen,
    openSideSheetState.workflowStatusBarOpen,
    currentNode,
  ]);

  // This workflow doesn't exist.
  if (workflow.loadingStatus.loading === LoadingStatusEnum.Failed) {
    navigate('/404');
    return null;
  }

  if (workflow.loadingStatus.loading !== LoadingStatusEnum.Succeeded) {
    return null;
  }

  // NOTE(vikram): This is a compliated bit of nonsense code. Because the
  // percentages are relative, we need to reset the base width to be the full
  // window width to take advantage of the helper function here. This ensures
  // that the ReactFlow canvas and the status bars below are the same width.
  // Here, `fullWindowWidth` refers to the full width of the viewport, which
  // is the current 100% + the width of the menu sidebar. This is a hack that
  // breaks the abstraction, but because the WorkflowStatusBar overlay is
  // absolute-positioned, it's required in order to align the content with
  // the status bar's width.
  const fullWindowWidth = `calc(100% + ${MenuSidebarOffset})`;
  const contentWidth = getBottomSideSheetWidth(
    openSideSheetState.workflowStatusBarOpen,
    fullWindowWidth
  );
  let contentBottomOffsetInPx;

  if (openSideSheetState.bottomSideSheetOpen) {
    contentBottomOffsetInPx = `${BottomSidebarHeightInPx + 20}px`;
  } else {
    contentBottomOffsetInPx = `${BottomSidebarHeaderHeightInPx + 20}px`;
  }

  const getNodeLabel = () => {
    if (
      currentNode.type === NodeType.TableArtifact ||
      currentNode.type === NodeType.FloatArtifact ||
      currentNode.type === NodeType.BoolArtifact ||
      currentNode.type === NodeType.JsonArtifact
    ) {
      return selectedDag.artifacts[currentNode.id].name;
    } else {
      return selectedDag.operators[currentNode.id].name;
    }
  };

  const getNodeActionButton = () => {
    if (currentNode.type === NodeType.TableArtifact) {
      // Since workflow is pending, it doesn't have a result set yet.
      let artifactResultData: Data | null = null;
      if (artifactResult?.result && artifactResult.result.data.length > 0) {
        artifactResultData = JSON.parse(artifactResult.result.data);
      }

      return (
        <Button
          onClick={() =>
            exportCsv(artifactResultData, getNodeLabel().replace(' ', '_'))
          }
        >
          Export CSV
        </Button>
      );
    }

    return null;
  };

  return (
    <DefaultLayout user={user}>
      <Box
        sx={{
          display: 'flex',
          width: contentWidth,
          height: '100%',
          flexDirection: 'column',
        }}
      >
        {workflow.selectedDag && (
          <WorkflowHeader user={user} workflowDag={workflow.selectedDag} />
        )}

        <Divider />

        <Box
          sx={{
            flex: 1,
            mt: 2,
            p: 3,
            mb: contentBottomOffsetInPx,
            backgroundColor: 'gray.50',
          }}
        >
          <ReactFlowProvider>
            <ReactFlowCanvas
              nodes={dagLayoutElements.nodes}
              edges={dagLayoutElements.edges}
              switchSideSheet={switchSideSheet}
              onPaneClicked={onPaneClicked}
            />
          </ReactFlowProvider>
        </Box>
      </Box>

      {currentNode.type !== NodeType.None && (
        <AqueductSidebar
          zIndex={10}
          position={SidebarPosition.bottom}
          getSideSheetTitle={getNodeLabel}
          getSideSheetHeadingContent={getNodeActionButton}
        >
          {getDataSideSheetContent(user, currentNode)}
        </AqueductSidebar>
      )}

      <WorkflowStatusBar user={user} />
    </DefaultLayout>
  );
};

export default WorkflowPage;
