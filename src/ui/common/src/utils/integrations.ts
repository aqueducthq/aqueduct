import { useAqueductConsts } from '../components/hooks/useAqueductConsts';
import UserProfile from './auth';

const { apiAddress } = useAqueductConsts();

export type Integration = {
  id: string;
  service: Service;
  name: string;
  config: IntegrationConfig;
  createdAt: number;
  validated: boolean;
};

export type PostgresConfig = {
  host: string;
  database: string;
  username: string;
  password?: string;
};

export type SnowflakeConfig = {
  account_identifier: string;
  warehouse: string;
  database: string;
  username: string;
  password?: string;
};

export type RedshiftConfig = {
  host: string;
  port: string;
  database: string;
  username: string;
  password?: string;
};

export type BigQueryConfig = {
  project_id: string;
  service_account_credentials?: string;
};

export type MySqlConfig = {
  host: string;
  port: string;
  database: string;
  username: string;
  password?: string;
};

export type MariaDbConfig = {
  host: string;
  port: string;
  database: string;
  username: string;
  password?: string;
};

export type SqlServerConfig = {
  host: string;
  port: string;
  database: string;
  username: string;
  password?: string;
};

export type GoogleSheetsConfig = {
  email: string;
  code?: string;
};

export type GithubConfig = {
  code?: string;
};

export type SalesforceConfig = {
  instance_url?: string;
  code?: string;
};

export type S3Config = {
  bucket: string;
  access_key_id: string;
  secret_access_key: string;
};

export type AqueductDemoConfig = Record<string, never>;

export type AirflowConfig = {
  host: string;
  username: string;
  password: string;
};

export type IntegrationConfig =
  | PostgresConfig
  | SnowflakeConfig
  | RedshiftConfig
  | BigQueryConfig
  | MySqlConfig
  | MariaDbConfig
  | SqlServerConfig
  | GoogleSheetsConfig
  | SalesforceConfig
  | S3Config
  | AqueductDemoConfig
  | AirflowConfig;

export type Service =
  | 'Postgres'
  | 'Snowflake'
  | 'Redshift'
  | 'BigQuery'
  | 'MySQL'
  | 'MariaDB'
  | 'S3'
  | 'CSV'
  | 'Aqueduct Demo'
  | 'Airflow';

type Info = {
  logo: string;
  activated: boolean;
};

export type ServiceInfoMap = {
  [key: string]: Info;
};

export type FileData = {
  name: string;
  data: string;
};

export type CSVConfig = {
  name: string;
  csv: FileData;
};

export async function addTable(
  user: UserProfile,
  integrationId: string,
  config: CSVConfig
): Promise<void> {
  const res = await fetch(
    `${apiAddress}/api/integration/${integrationId}/create`,
    {
      method: 'POST',
      headers: {
        'api-key': user.apiKey,
        'table-name': config.name,
      },
      body: config.csv.data,
    }
  );
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message);
  }
}

export async function fetchRepos(
  user: UserProfile
): Promise<[string[], string]> {
  try {
    const res = await fetch(`${apiAddress}/api/integrations/github/repos`, {
      method: 'GET',
      headers: {
        'api-key': user.apiKey,
      },
    });

    if (!res.ok) {
      return [[], await res.text()];
    }

    const body = await res.json();
    return [body.repos, ''];
  } catch (err) {
    return [[], err];
  }
}

export async function fetchBranches(
  user: UserProfile,
  repo: string
): Promise<[string[], string]> {
  try {
    const res = await fetch(`${apiAddress}/api/integrations/github/branches`, {
      method: 'GET',
      headers: {
        'api-key': user.apiKey,
        'github-repo': repo,
      },
    });

    if (!res.ok) {
      return [[], await res.text()];
    }

    const body = await res.json();
    return [body.branches, ''];
  } catch (err) {
    return [[], err];
  }
}

export async function connectIntegration(
  user: UserProfile,
  service: Service,
  name: string,
  config: IntegrationConfig
): Promise<void> {
  const res = await fetch(`${apiAddress}/api/integration/connect`, {
    method: 'POST',
    headers: {
      'api-key': user.apiKey,
      'integration-name': name,
      'integration-service': service,
      'integration-config': JSON.stringify(config),
    },
  });

  if (!res.ok) {
    const message = await res.text();
    throw new Error(message);
  }
}

export const SupportedIntegrations: ServiceInfoMap = {
  ['Postgres']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/440px-Postgresql_elephant.svg.png',
    activated: true,
  },
  ['Snowflake']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/51-513957_periscope-data-partners-snowflake-computing-logo.png',
    activated: true,
  },
  ['Redshift']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/amazon-redshift.png',
    activated: true,
  },
  ['BigQuery']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/google-bigquery-logo-1.svg',
    activated: true,
  },
  ['MySQL']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/mysql.png',
    activated: true,
  },
  ['MariaDB']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/mariadb.png',
    activated: true,
  },
  ['S3']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/s3.png',
    activated: true,
  },
  ['Aqueduct Demo']: {
    logo: '/assets/aqueduct.png',
    activated: true,
  },
  ['SQLite']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/sqlite_banner.png',
    activated: false,
  },
  ['Airflow']: {
    logo: 'https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/pages/integrations/sqlite_banner.png',
    activated: true,
  },
};

// Helper function to format integration service
export function formatService(service: string): string {
  service = service.toLowerCase();
  return service.replace(/ /g, '_');
}
