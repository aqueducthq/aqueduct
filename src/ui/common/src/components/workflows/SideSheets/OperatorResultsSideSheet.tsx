import { faCircleDown } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { Alert, Snackbar } from '@mui/material';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useSelector } from 'react-redux';

import { SelectedNode } from '../../../reducers/nodeSelection';
import { RootState } from '../../../stores/store';
import * as style from '../../../styles/markdown.module.css';
import UserProfile from '../../../utils/auth';
import {
  ExportFunctionStatus,
  GoogleSheetsExtractParams,
  GoogleSheetsLoadParams,
  handleExportFunction,
  OperatorType,
  RelationalDBExtractParams,
  RelationalDBLoadParams,
} from '../../../utils/operators';
import DataPreviewer from '../../layouts/data_previewer';
import { BottomSidebarHeaderHeightInPx } from '../../layouts/sidebar/AqueductSidebar';
import { Button } from '../../primitives/Button.styles';
import { Tab, Tabs } from '../../primitives/Tabs.styles';
import LogViewer from '../log_viewer';
import Status from '../workflowStatus';

interface Props {
  user: UserProfile;
  currentNode: SelectedNode;
}

const OperatorResultsSideSheet: React.FC<Props> = ({ user, currentNode }) => {
  const workflow = useSelector((state: RootState) => state.workflowReducer);
  const artifactResults = useSelector(
    (state: RootState) => state.workflowReducer.artifactResults
  );
  const operator = (workflow.selectedDag?.operators ?? {})[currentNode.id];
  const logs =
    workflow.operatorResults[currentNode.id]?.result?.user_logs ?? {};
  const operatorError = workflow.operatorResults[currentNode.id]?.result?.error;
  const integrations = useSelector(
    (state: RootState) => state.integrationsReducer
  );

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState<ExportFunctionStatus>();
  const handleToastClose = () => {
    setShowToast(false);
  };

  const operatorSpec = operator.spec;
  const status = workflow.operatorResults[currentNode.id]?.result?.status;

  let spec, integration, actions;

  // Load the operator spec, which has a different variable name depending on
  // the type of the operator.
  switch (operatorSpec.type) {
    case OperatorType.Extract:
      spec = operatorSpec.extract;
      break;
    case OperatorType.Load:
      spec = operatorSpec.load;
      break;
    case OperatorType.Metric:
      spec = operatorSpec.metric.function;
      break;
    case OperatorType.Check:
      spec = operatorSpec.check.function;
      break;
    case OperatorType.Function:
      spec = operatorSpec.function;
      break;
  }

  // The only action we currently support is downloading the function, which
  // is only valid for function operators, metrics, and checks.
  if (
    operatorSpec.type === OperatorType.Function ||
    operatorSpec.type === OperatorType.Metric ||
    operatorSpec.type === OperatorType.Check
  ) {
    const functionFileName = `${operator.name ?? 'function'}.zip`;
    actions = (
      <>
        <Button
          onClick={async () => {
            const exportFunctionResult: ExportFunctionStatus =
              await handleExportFunction(
                user,
                currentNode.id,
                functionFileName
              );

            setToastMessage(exportFunctionResult);
            setShowToast(true);
          }}
          color="secondary"
        >
          <FontAwesomeIcon icon={faCircleDown} />
          <Typography sx={{ ml: 1 }}>{functionFileName}</Typography>
        </Button>

        <Snackbar
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          open={showToast}
          onClose={handleToastClose}
          key={'function-op-sidesheet-snackbar'}
          autoHideDuration={6000}
        >
          <Alert
            onClose={handleToastClose}
            severity={
              toastMessage?.loadingStatus === 'success' ? 'success' : 'error'
            }
            sx={{ width: '100%' }}
          >
            {toastMessage?.message}
          </Alert>
        </Snackbar>
      </>
    );
  }

  const operatorParams = [];
  // When we have an IO operator (an extract or a load), we need to configure
  // the input/output parameters, which depend on whether this operator was
  // connecting to Google Sheets or a relational database. Based on that
  // metadata, we populate the `operatorParams` list, which we then use to
  // generate a view of the configuration parameters below.
  if (
    operatorSpec.type === OperatorType.Extract ||
    operatorSpec.type === OperatorType.Load
  ) {
    const filteredIntegrations = integrations.integrations.filter(
      (integration) => {
        return integration.id === spec.integration_id;
      }
    );

    integration = filteredIntegrations[0]; // There can only be one result.
    operatorParams.push(['Integration', integration.name]);

    switch (integration.service) {
      case 'Google Sheets':
        if (operatorSpec.type === OperatorType.Extract) {
          operatorParams.push([
            'Spreadsheet ID',
            (spec.parameters as GoogleSheetsExtractParams).spreadsheet_id,
          ]);
        } else {
          operatorParams.push([
            'Filepath',
            (spec.parameters as GoogleSheetsLoadParams).filepath,
          ]);
        }

        operatorParams.push([
          'Mode',
          (spec.parameters as GoogleSheetsLoadParams).save_mode,
        ]);

        break;
      default:
        if (operatorSpec.type === OperatorType.Extract) {
          operatorParams.push([
            'Query',
            <Box sx={{ maxWidth: '600px' }} key="sql-query">
              <code>
                {(spec.parameters as RelationalDBExtractParams).query}
              </code>
            </Box>,
          ]);
        } else {
          operatorParams.push([
            'Table Name',
            (spec.parameters as RelationalDBLoadParams).table,
          ]);
        }
        operatorParams.push([
          'Mode',
          (spec.parameters as RelationalDBLoadParams).update_mode,
        ]);
    }
  } else if (operatorSpec.type === OperatorType.Check) {
    operatorParams.push(['Level', operatorSpec.check?.level]);
  }

  if (
    operatorSpec.type === OperatorType.Function ||
    operatorSpec.type === OperatorType.Metric ||
    operatorSpec.type === OperatorType.Check
  ) {
    operatorParams.push(['Function Language', spec.language]);
    operatorParams.push(['Function Granularity', spec.granularity]);
    if (spec.custom_args) {
      operatorParams.push(['Function Custom Arguments', spec.custom_args]);
    }
  }

  // This converts from the `operatorParams` list above into a sequence of
  // `Box`es that show key/value pairs of the parameters that govern the
  // behavior of this operator.
  const paramsView = operatorParams.map((parameter) => {
    const valueIsString = typeof parameter[1] === 'string';
    return (
      // Only display key and value on the same line if we receive a
      // string value.
      <Box
        sx={{ display: valueIsString ? 'flex' : '', mb: 1 }}
        key={parameter[0]}
      >
        <Typography variant="body1" style={{ fontWeight: 'bold' }}>
          {parameter[0]}:
        </Typography>
        <Box sx={{ ml: valueIsString ? 2 : 0 }}>
          {
            // parameter[1] either has to be a string or a
            // React.ReactElement.
            valueIsString ? (
              <Typography variant="body1" style={{ fontFamily: 'Monospace' }}>
                {parameter[1]}
              </Typography>
            ) : (
              parameter[1]
            )
          }
        </Box>
      </Box>
    );
  });

  // `selectedIndex` is used to control which tab is selected in the `Tabs`
  // pane below.
  const [selectedIndex, setSelectedIndex] = useState(0);
  const handleTabClick = (event: React.SyntheticEvent, index: number) => {
    event.preventDefault();
    setSelectedIndex(index);
  };

  // Reset tab selection when the node changes.
  useEffect(() => {
    setSelectedIndex(0);
  }, [currentNode.id]);

  const tableTabs = [];
  if (operator) {
    // Put together all inputs and outputs in an array
    const inputs = operator.inputs;
    const outputs = operator.outputs;

    for (const outputArtifactId of outputs) {
      tableTabs.push(
        <Tab
          key={outputArtifactId}
          label={`Output (${workflow.selectedDag?.artifacts[outputArtifactId]?.name})`}
        />
      );
    }

    for (const inputArtifactId of inputs) {
      tableTabs.push(
        <Tab
          key={inputArtifactId}
          label={`Input (${workflow.selectedDag?.artifacts[inputArtifactId]?.name})`}
        />
      );
    }
  }

  const artifactIds = [...operator.outputs, ...operator.inputs];

  const tabs = [<Tab key="overview" label="Overview" />].concat(
    tableTabs.concat([<Tab key="logs" label="Logs" />])
  );
  const tabContentHeight = 'calc(100% - 48px)'; // 48px is the size of the Tabs bar.

  // This returns a list of `Box` components (each with the role
  // `tabpanel`), each of which corresponds to a `DataPreviewer` for the
  // corresponding input or output for this operator.
  const tableBoxes = artifactIds.map((artifactId, idx) => {
    let error;
    if (operator.outputs.includes(artifactId)) {
      // Only show the error on the outputs, not the inputs.
      error = operatorError;
    }

    return (
      <Box
        key={idx}
        role="tabpanel"
        hidden={selectedIndex !== idx + 1}
        sx={{ height: '100%', pb: 2, overflow: 'auto' }}
      >
        <DataPreviewer
          previewData={artifactResults[artifactId]}
          error={error}
        />
      </Box>
    );
  });

  return (
    <Box
      p={1}
      sx={{
        height: `calc(100% - ${BottomSidebarHeaderHeightInPx}px)`,
      }}
    >
      <Tabs
        value={selectedIndex}
        onChange={handleTabClick}
        sx={{ mb: 1 }}
        scrollButtons="auto"
        variant="scrollable"
      >
        {tabs}
      </Tabs>

      <Box sx={{ height: tabContentHeight, p: 1 }}>
        <Box role="tabpanel" hidden={selectedIndex !== 0}>
          {status && (
            <Box sx={{ display: 'flex', flexDirection: 'row', mb: 2 }}>
              <Typography variant="body1" style={{ fontWeight: 'bold' }}>
                Status:
              </Typography>
              <Box sx={{ ml: 2 }}>
                <Status status={status} />
              </Box>
            </Box>
          )}
          {operator.description && (
            <ReactMarkdown className={style.reactMarkdown}>
              {operator.description}
            </ReactMarkdown>
          )}
          <Box py={1}>{paramsView}</Box>

          <Box>{actions}</Box>
        </Box>

        {tableBoxes}

        <Box
          role="tabpanel"
          hidden={selectedIndex !== tabs.length - 1}
          sx={{ height: '100%', overflow: 'auto' }}
        >
          <LogViewer logs={logs} err={operatorError} />
        </Box>
      </Box>
    </Box>
  );
};

export default OperatorResultsSideSheet;
