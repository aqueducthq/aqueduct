import { WorkflowState } from '../reducers/workflow';
import ExecutionStatus from './shared';

export enum ArtifactType {
  Table = 'table',
  Float = 'float',
  Bool = 'boolean',
  Json = 'json',
}

export type Spec = {
  table?: Record<string, string>;
  metric?: Record<string, string>;
  bool?: Record<string, string>;
  type: ArtifactType;
};

export type Artifact = {
  id: string;
  name: string;
  description: string;
  spec: Spec;
};

export type Schema = { [col_name: string]: string }[];

export type GetArtifactResultResponse = {
  status: ExecutionStatus;
  schema: Schema;
  data: string;
};

// Takes the ID of an artifact in our DAG and the state of the currently
// selected workflow and returns the ID of the operator that is responsible for
// creating the artifact.
export const getUpstreamOperator = (
  workflowState: WorkflowState,
  artifactId: string
): string => {
  let result: string;

  // Load all operators in the current dag version and iterate through
  // them.
  const operators = workflowState.selectedDag?.operators;

  for (const operator of Object.values(operators)) {
    // Check if this particular operator was the one responsible for
    // creating the artifact we care about. If so, pull the
    // `GetOperatorResultResponse` from the `workflowReducer` state and
    // retrieve the error from that response.
    if (operator.outputs.includes(artifactId)) {
      result = operator.id;
      break;
    }
  }

  return result;
};
