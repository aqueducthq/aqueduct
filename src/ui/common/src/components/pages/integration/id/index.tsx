import { faRefresh, faUpload } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  Alert,
  Autocomplete,
  Link,
  TextField,
  Typography,
} from '@mui/material';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { DataGrid } from '@mui/x-data-grid';
import React, { SyntheticEvent, useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';

import { DetailIntegrationCard } from '../../../../components/integrations/cards/detailCard';
import { AddTableDialog } from '../../../../components/integrations/dialogs/dialog';
import DefaultLayout from '../../../../components/layouts/default';
import { handleLoadIntegrations } from '../../../../reducers/integrations';
import {
  handleLoadIntegrationTable,
  tableKeyFn,
} from '../../../../reducers/integrationTableData';
import { handleLoadIntegrationTables } from '../../../../reducers/integrationTables';
import { AppDispatch, RootState } from '../../../../stores/store';
import UserProfile from '../../../../utils/auth';
import { Integration } from '../../../../utils/integrations';
import ExecutionStatus from '../../../../utils/shared';
import { Button } from '../../../primitives/Button.styles';

type IntegrationDetailsPageProps = {
  user: UserProfile;
};

const IntegrationDetailsPage: React.FC<IntegrationDetailsPageProps> = ({
  user,
}) => {
  const dispatch: AppDispatch = useDispatch();
  const integrationId: string = useParams().id;
  const [table, setTable] = useState<string>('');
  const [showDialog, setShowDialog] = useState(false);

  // Using the ListIntegrationsRoute.
  // ENG-1036: We should create a route where we can pass in the integrationId and get the associated metadata and switch to using that.
  useEffect(() => {
    dispatch(handleLoadIntegrations({ apiKey: user.apiKey }));
    dispatch(
      handleLoadIntegrationTables({
        apiKey: user.apiKey,
        integrationId: integrationId,
      })
    );
  }, []);

  const integrations = useSelector(
    (state: RootState) => state.integrationsReducer.integrations
  );
  const integrationTables = useSelector(
    (state: RootState) => state.integrationTablesReducer.integrationTables
  );
  const tableListStatus = useSelector(
    (state: RootState) => state.integrationTablesReducer.thunkState
  );

  useEffect(() => {
    dispatch(
      handleLoadIntegrationTable({
        apiKey: user.apiKey,
        integrationId: integrationId,
        table: table,
      })
    );
  }, [table]);

  const tableKey = tableKeyFn(table);
  const [tableDataStatus, retrievedTableData] = useSelector(
    (state: RootState) => {
      let status = ExecutionStatus.Pending;
      if (state.integrationTableDataReducer.hasOwnProperty(tableKey)) {
        status = state.integrationTableDataReducer[tableKey].status;
      }
      let returnedData = null;
      if (table !== '' && status === ExecutionStatus.Succeeded) {
        const data = state.integrationTableDataReducer[tableKey].data;
        if (data !== undefined && data !== '') {
          returnedData = JSON.parse(data);
        }
      } else if (table !== '' && status === ExecutionStatus.Failed) {
        returnedData = state.integrationTableDataReducer[tableKey].err;
      }
      return [status, returnedData];
    }
  );

  const loading = tableListStatus === ExecutionStatus.Pending;

  const forceLoadTableList = async () => {
    if (!loading) {
      dispatch(
        handleLoadIntegrationTables({
          apiKey: user.apiKey,
          integrationId: integrationId,
          forceLoad: true,
        })
      );
    }
  };

  // ENG-1052: We should update the route handler to give us the data in the format we want rather than needing to do post-processing in the FE side.
  const dataTable = {
    cols: [],
    rows: [],
  };
  if (
    table !== '' &&
    retrievedTableData &&
    tableDataStatus === ExecutionStatus.Succeeded
  ) {
    dataTable.cols.push({ field: '_id', hide: true });
    retrievedTableData.schema.fields.forEach((col, _) => {
      const header = `${col.name} (${col.type})`;
      dataTable.cols.push({
        field: col.name,
        headerName: header,
        minWidth: `${10 * header.length}px`,
        flex: 1,
      });
    });
    retrievedTableData.data.forEach((data, idx) => {
      data['_id'] = idx;
      dataTable.rows.push(data);
    });
  }

  let selectedIntegration = null;

  if (integrations) {
    (integrations as Integration[]).forEach((integration) => {
      if (integration.id === integrationId) {
        selectedIntegration = integration;
      }
    });
  }

  const handleChange = (
    event: SyntheticEvent<Element, Event>,
    newValue: string
  ) => {
    setTable(newValue);
  };

  const hasTable = table != null && table !== '';

  useEffect(() => {
    if (selectedIntegration && selectedIntegration.name) {
      document.title = `Integration Details: ${selectedIntegration.name} | Aqueduct`;
    } else {
      document.title = `Integration Details | Aqueduct`;
    }
  }, []);

  if (!integrations || !selectedIntegration) {
    return null;
  }

  let preview = (
    <Alert severity="warning" sx={{ width: '80%' }}>
      <>
        We currently do not support listing data in an S3 bucket. But don&apos;t
        worry&mdash;we&apos;re working on adding this feature! If you have
        questions, comments or would like to learn more about what we&apos;re
        building, please{' '}
      </>
      <Link href="mailto:hello@aqueducthq.com">reach out</Link>
      <>, </>
      <Link href="https://join.slack.com/t/aqueductusers/shared_invite/zt-11hby91cx-cpmgfK0qfXqEYXv25hqD6A">
        join our Slack channel
      </Link>
      <>, or </>
      <Link href="https://github.com/aqueducthq/aqueduct/issues/new">
        start a conversation on GitHub channel
      </Link>
      <>.</>
    </Alert>
  );

  if (selectedIntegration.service !== 'S3') {
    preview = (
      <Box sx={{ mt: 4 }}>
        <Typography variant="h4" gutterBottom component="div">
          Preview
        </Typography>
        <Box>
          <Autocomplete
            disablePortal
            value={table}
            sx={{
              verticalAlign: 'middle',
              display: 'inline-block',
              width: '35ch',
            }}
            onChange={handleChange}
            options={integrationTables}
            loading={loading}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Base Table"
                InputProps={{
                  ...params.InputProps,
                  endAdornment: (
                    <React.Fragment>
                      {params.InputProps.endAdornment}
                    </React.Fragment>
                  ),
                }}
              />
            )}
          />
          <FontAwesomeIcon
            className={loading ? 'fa-spin' : ''}
            style={{
              marginLeft: '15px',
              fontSize: '2em',
              verticalAlign: 'middle',
              display: 'inline-block',
              color: loading ? 'grey' : 'black',
              cursor: loading ? 'default' : 'pointer',
            }}
            icon={faRefresh}
            onClick={forceLoadTableList}
          />
        </Box>

        <Box sx={{ mt: 3 }}>
          {hasTable && tableDataStatus === ExecutionStatus.Pending && (
            <Box sx={{ display: 'flex', flexDirection: 'row', mt: 3 }}>
              <CircularProgress size={30} />
              <Typography sx={{ ml: 2 }}>
                Loading table <b>{table}</b>...
              </Typography>
            </Box>
          )}
          {hasTable && tableDataStatus === ExecutionStatus.Failed && (
            <Alert style={{ marginTop: '10px' }} severity="error">
              Table <b>{table}</b> failed to load. Try refreshing the page.{' '}
              <br />
              Error: {retrievedTableData}
            </Alert>
          )}
          {hasTable &&
            tableDataStatus === ExecutionStatus.Succeeded &&
            retrievedTableData !== '' && (
              <div style={{ height: '50vh', width: 'calc(100% - 25px)' }}>
                <DataGrid
                  getRowId={(row) => row._id}
                  rows={dataTable.rows}
                  columns={dataTable.cols}
                  pageSize={50}
                  rowsPerPageOptions={[50]}
                  disableSelectionOnClick
                />
              </div>
            )}
        </Box>
      </Box>
    );
  }

  return (
    <DefaultLayout user={user}>
      <Box>
        <Typography variant="h2" gutterBottom component="div">
          Integration Details
        </Typography>

        <DetailIntegrationCard integration={selectedIntegration} />

        {selectedIntegration.name === 'aqueduct_demo' && (
          <Button variant="contained" onClick={() => setShowDialog(true)}>
            <FontAwesomeIcon icon={faUpload} />
            <Typography sx={{ ml: 1 }}>Add CSV</Typography>
          </Button>
        )}

        {showDialog && (
          <AddTableDialog
            user={user}
            integrationId={selectedIntegration.id}
            onCloseDialog={() => setShowDialog(false)}
            onConnect={() => forceLoadTableList()}
          />
        )}
      </Box>
      {preview}
    </DefaultLayout>
  );
};

export default IntegrationDetailsPage;
