import { Edge, Node } from 'react-flow-renderer';
import { Position } from 'react-flow-renderer';

import { useAqueductConsts } from '../components/hooks/useAqueductConsts';
import AqueductBezier from '../components/workflows/edges/AqueductBezier';
import AqueductQuadratic from '../components/workflows/edges/AqueductQuadratic';
import AqueductStraight from '../components/workflows/edges/AqueductStraight';
import {
  ArtifactTypeToNodeTypeMap,
  OperatorTypeToNodeTypeMap,
} from '../reducers/nodeSelection';
import { Artifact } from './artifacts';
import { Operator, OperatorType } from './operators';

const { apiAddress } = useAqueductConsts();

export const EdgeTypes = {
  quadratic: AqueductQuadratic,
  straight: AqueductStraight,
  curved: AqueductBezier,
};

export enum ReactflowNodeType {
  Operator = 'operator',
  Artifact = 'artifact',
}

export type ReactFlowNodeData = {
  onChange: () => void;
  onConnect: (any) => void;
  targetHandlePosition?: Position;
  nodeType: ReactflowNodeType;
  nodeId: string;
  label?: string;
};

// These are generic dag supports
type NodePos = { x: number; y: number };

function getOperatorNode(
  op: Operator,
  pos: NodePos,
  onChange: () => void,
  onConnect: (any) => void
): Node<ReactFlowNodeData> {
  return {
    id: op.id,
    type: OperatorTypeToNodeTypeMap[op.spec.type],
    draggable: false,
    data: {
      nodeType: ReactflowNodeType.Operator,
      onChange,
      onConnect,
      nodeId: op.id,
      label: op.name,
    },
    position: pos,
  };
}

function getArtifactNode(
  artf: Artifact,
  pos: NodePos,
  onChange: () => void,
  onConnect: (any) => void
): Node<ReactFlowNodeData> {
  return {
    id: artf.id,
    type: ArtifactTypeToNodeTypeMap[artf.spec.type],
    draggable: false,
    data: {
      nodeType: ReactflowNodeType.Artifact,
      onChange,
      onConnect,
      nodeId: artf.id,
      label: artf.name,
    },
    position: pos,
  };
}

function getEdges(operators: { [id: string]: Operator }): Edge[] {
  const results = [];
  Object.values(operators).forEach((op) => {
    op.inputs.forEach((artfId) => {
      results.push({
        id: `${artfId}-${op.id}`,
        type: 'curved', // Op inputs are curved edges
        source: artfId,
        target: op.id,
      });
    });
    op.outputs.forEach((artfId) => {
      results.push({
        id: `${op.id}-${artfId}`,
        type: 'straight',
        source: op.id,
        target: artfId,
      });
    });
  });
  return results;
}

async function getPositions(
  operators: { [id: string]: Operator },
  apiKey: string
): Promise<[{ [opId: string]: NodePos }, { [artfId: string]: NodePos }]> {
  try {
    const response = await fetch(`${apiAddress}/api/positioning`, {
      method: 'POST',
      headers: {
        'api-key': apiKey,
      },
      body: JSON.stringify(operators),
    });
    const json = await response.json();
    return [json['operator_positions'], json['artifact_positions']];
  } catch (e) {
    console.error(e);
  }
}

export const getDagLayoutElements = async (
  operators: { [id: string]: Operator },
  artifacts: { [id: string]: Artifact },
  onChange: () => void,
  onConnect: (any) => void,
  apiKey: string
): Promise<{ nodes: Node<ReactFlowNodeData>[]; edges: Edge[] }> => {
  const [opPositions, artfPositions] = await getPositions(operators, apiKey);

  // Do not display any parameter operators, only the artifacts.
  const opNodes = Object.values(operators)
    .filter((op) => {
      return op.spec.type != OperatorType.Param;
    })
    .map((op) => getOperatorNode(op, opPositions[op.id], onChange, onConnect));
  const artfNodes = Object.values(artifacts).map((artf) =>
    getArtifactNode(artf, artfPositions[artf.id], onChange, onConnect)
  );

  const edges = getEdges(operators);
  return { nodes: opNodes.concat(artfNodes), edges: edges };
};
