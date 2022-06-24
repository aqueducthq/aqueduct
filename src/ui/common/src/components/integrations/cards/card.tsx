import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import React from 'react';

import { DataPreviewInfo } from '../../../utils/data';
import {
  Integration,
  SupportedIntegrations,
} from '../../../utils/integrations';
import WorkflowStatus from '../../workflows/workflowStatus';
import { AirflowCard } from './airflowCard';
import { AqueductDemoCard } from './aqueductDemoCard';
import { BigQueryCard } from './bigqueryCard';
import { LoadSpecsCard } from './loadSpecCard';
import { MariaDbCard } from './mariadbCard';
import { MySqlCard } from './mysqlCard';
import { PostgresCard } from './postgresCard';
import { RedshiftCard } from './redshiftCard';
import { S3Card } from './s3Card';
import { SnowflakeCard } from './snowflakeCard';

type DataProps = {
  dataPreviewInfo: DataPreviewInfo;
};

export const dataCardName = (dataPreviewInfo: DataPreviewInfo): string =>
  `${dataPreviewInfo.workflow_name}: ${dataPreviewInfo.artifact_name}`;

export const DataCard: React.FC<DataProps> = ({ dataPreviewInfo }) => {
  const dataPreviewInfoVersions = Object.keys(dataPreviewInfo.versions);
  if (dataPreviewInfoVersions.length > 0) {
    let latestTimestamp = 0;
    let latestVersionUUID = null;
    dataPreviewInfoVersions.forEach((uuid) => {
      if (latestTimestamp < dataPreviewInfo.versions[uuid].timestamp) {
        latestTimestamp = dataPreviewInfo.versions[uuid].timestamp;
        latestVersionUUID = uuid;
      }
    });
    const workflowId = dataPreviewInfo.workflow_id;
    return (
      <Link underline="none" color="inherit" href={`/workflow/${workflowId}`}>
        <Box sx={{ display: 'flex', flexDirection: 'column', width: '900px' }}>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'row',
              justifyContent: 'space-between',
            }}
          >
            <Typography
              variant="h4"
              gutterBottom
              component="div"
              sx={{
                fontFamily: 'Monospace',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {dataCardName(dataPreviewInfo)}
            </Typography>
          </Box>

          <Typography variant="body1">
            <strong>Status: </strong>
          </Typography>

          <WorkflowStatus
            status={dataPreviewInfo.versions[latestVersionUUID].status}
          />

          <Typography variant="body1">
            <strong>Saved at: </strong>
            {new Date(
              dataPreviewInfo.versions[latestVersionUUID].timestamp * 1000
            ).toLocaleString()}
          </Typography>

          <LoadSpecsCard loadSpecs={dataPreviewInfo.load_specs} />
        </Box>
      </Link>
    );
  }
  return null;
};

type IntegrationProps = {
  integration: Integration;
};

export const IntegrationCard: React.FC<IntegrationProps> = ({
  integration,
}) => {
  let serviceCard;
  switch (integration.service) {
    case 'Postgres':
      serviceCard = <PostgresCard integration={integration} />;
      break;
    case 'Snowflake':
      serviceCard = <SnowflakeCard integration={integration} />;
      break;
    case 'Aqueduct Demo':
      serviceCard = <AqueductDemoCard integration={integration} />;
      break;
    case 'MySQL':
      serviceCard = <MySqlCard integration={integration} />;
      break;
    case 'Redshift':
      serviceCard = <RedshiftCard integration={integration} />;
      break;
    case 'MariaDB':
      serviceCard = <MariaDbCard integration={integration} />;
      break;
    case 'BigQuery':
      serviceCard = <BigQueryCard integration={integration} />;
      break;
    case 'S3':
      serviceCard = <S3Card integration={integration} />;
      break;
    case 'Airflow':
      serviceCard = <AirflowCard integration={integration} />;
      break;  
    default:
      serviceCard = null;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', width: '900px' }}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'space-between',
        }}
      >
        <Typography sx={{ fontFamily: 'Monospace' }} variant="h4">
          {integration.name}
        </Typography>
        <img
          height="45px"
          src={SupportedIntegrations[integration.service].logo}
        />
      </Box>

      {serviceCard}

      <Typography variant="body1">
        <strong>Connected On: </strong>
        {new Date(integration.createdAt * 1000).toLocaleString()}
      </Typography>
    </Box>
  );
};
