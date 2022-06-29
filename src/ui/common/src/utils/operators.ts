import { useAqueductConsts } from '../components/hooks/useAqueductConsts';
import UserProfile from './auth';
import ExecutionStatus from './shared';

export enum OperatorType {
  Function = 'function',
  Extract = 'extract',
  Load = 'load',
  Metric = 'metric',
  Check = 'check',
  Param = 'param',
}

export enum FunctionType {
  File = 'file',
  Github = 'github',
  BuiltIn = 'built_in',
}

export enum FunctionGranularity {
  Table = 'table',
  Row = 'row',
}

export type GithubMetadata = {
  owner: string;
  repo: string;
  branch: string;
  path: string;
  commit_id: string;
};

export type FunctionOp = {
  type: FunctionType;
  language: string;
  granularity: FunctionGranularity;
  s3_path: string;
  github_metadata?: GithubMetadata;
  custom_args: string;
};

export enum CheckLevel {
  Error = 'error',
  Warning = 'warning',
}

export type Metric = {
  function: FunctionOp;
};

export type Check = {
  level: CheckLevel;
  function: FunctionOp;
};

export enum ServiceType {
  Postgres = 'Postgres',
  Snowflake = 'Snowflake',
  AqueductDemo = 'Aqueduct Demo',
  Github = 'Github',
}

export type ExtractParameters =
  | RelationalDBExtractParams
  | GoogleSheetsExtractParams;

export type RelationalDBExtractParams = {
  query: string;
  github_metadata?: GithubMetadata;
};

export type GoogleSheetsExtractParams = {
  spreadsheet_id: string;
  github_metadata?: GithubMetadata;
};

export type Extract = {
  service: ServiceType;
  integration_id: string;
  // This is a json serialized string of ExtractParams structs.
  // For now, we will dangerously assume the serialized string is always
  // consistent with the `service` field.
  parameters: ExtractParameters;
};

export type LoadParameters = RelationalDBLoadParams | GoogleSheetsLoadParams;

export type RelationalDBLoadParams = {
  table: string;
  update_mode: string;
};

export type GoogleSheetsLoadParams = {
  filepath: string;
  save_mode: string;
};

export type Load = {
  service: ServiceType;
  integration_id: string;
  // This is a json serialized string of ExtractParams structs.
  // For now, we will dangerously assume the serialized string is always
  // consistent with the `service` field.
  parameters: LoadParameters;
};

export type OperatorSpec = {
  type: OperatorType;
  function?: FunctionOp;
  metric?: Metric;
  extract?: Extract;
  load?: Load;
  check?: Check;
};

export type Operator = {
  id: string;
  name: string;
  description: string;
  spec: OperatorSpec;

  inputs: string[];
  outputs: string[];
};

// This function `normalize` an arbitrary object (typically from an API call)
// to the `Operator` object that actually follows its type definition.
//
// For now, we only handle all lists / maps field. Ideally, we should
// handle all fields like `operator.id = operator?.id ?? ''`.
export function normalizeOperator(op): Operator {
  op.inputs = op?.inputs ?? [];
  op.outputs = op?.outputs ?? [];
  return op;
}

export type GetOperatorResultResponse = {
  status: ExecutionStatus;
  error: string;
  logs: { [name: string]: string };
};

const { apiAddress } = useAqueductConsts();

export async function exportFunction(
  user: UserProfile,
  operatorId: string
): Promise<Blob> {
  const res = await fetch(`${apiAddress}/api/function/${operatorId}/export`, {
    method: 'GET',
    headers: {
      'api-key': user.apiKey,
    },
  });

  if (!res.ok) {
    const message = await res.text();
    throw new Error(message);
  }

  return await res.blob();
}

export type ExportFunctionStatus = {
  loadingStatus: 'idle' | 'pending' | 'error' | 'success';
  message: string;
};

/**
 * Exports function code by operator id.
 * @param user the UserProfile in which to get the function for. (Currently logged in user)
 * @param operatorId the operator id of the function to fetch.
 * @param exportFileName the filename to save the exported function as.
 * @returns status of the exported function.
 */
export function handleExportFunction(
  user: UserProfile,
  operatorId: string,
  exportFileName: string
): Promise<ExportFunctionStatus> {
  return exportFunction(user, operatorId)
    .then((blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = exportFileName;
      a.click();
      return {
        loadingStatus: 'success',
        message: `Successfully exported ${exportFileName}.`,
      } as ExportFunctionStatus;
    })
    .catch((err) => {
      return {
        loadingStatus: 'error',
        message: `Unable to export function: ${err}`,
      } as ExportFunctionStatus;
    });
}
