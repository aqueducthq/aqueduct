import BoolArtifactNode from './BoolArtifactNode';
import CheckOperatorNode from './CheckOperatorNode';
import DatabaseNode from './DatabaseNode';
import FloatArtifactNode from './FloatArtifactNode';
import FunctionOperatorNode from './FunctionOperatorNode';
import JsonArtifactNode from './JsonArtifactNode';
import MetricOperatorNode from './MetricOperatorNode';
import TableArtifactNode from './TableArtifactNode';

export const nodeTypes = {
  database: DatabaseNode,
  tableArtifact: TableArtifactNode,
  floatArtifact: FloatArtifactNode,
  boolArtifact: BoolArtifactNode,
  jsonArtifact: JsonArtifactNode,
  function: FunctionOperatorNode,

  // These are generic DAG nodes
  functionOp: FunctionOperatorNode,
  extractOp: DatabaseNode,
  loadOp: DatabaseNode,
  metricOp: MetricOperatorNode,
  checkOp: CheckOperatorNode,
};

export default nodeTypes;
