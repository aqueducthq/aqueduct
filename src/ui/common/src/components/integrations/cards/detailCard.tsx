import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import React from 'react';

import {
  Integration,
  SupportedIntegrations,
} from '../../../utils/integrations';
import { AqueductDemoCard } from './aqueductDemoCard';
import { BigQueryCard } from './bigqueryCard';
import { MariaDbCard } from './mariadbCard';
import { MySqlCard } from './mysqlCard';
import { PostgresCard } from './postgresCard';
import { RedshiftCard } from './redshiftCard';
import { S3Card } from './s3Card';
import { SnowflakeCard } from './snowflakeCard';

type DetailIntegrationCardProps = {
  integration: Integration;
};

export const DetailIntegrationCard: React.FC<DetailIntegrationCardProps> = ({
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
    default:
      serviceCard = null;
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        width: '900px',
        mt: 2,
        mb: 2,
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'row' }}>
        <img
          height="45px"
          src={SupportedIntegrations[integration.service].logo}
        />
        <Box sx={{ ml: 3 }}>
          <Typography sx={{ fontFamily: 'Monospace' }} variant="h4">
            {integration.name}
          </Typography>

          <Typography variant="body1">
            <strong>Connected On: </strong>
            {new Date(integration.createdAt * 1000).toLocaleString()}
          </Typography>

          {serviceCard}
        </Box>
      </Box>
    </Box>
  );
};
