import { faPencil } from '@fortawesome/free-solid-svg-icons';
import React, { memo } from 'react';

import { ReactFlowNodeData } from '../../../utils/reactflow';
import Node from './Node';

type Props = {
  data: ReactFlowNodeData;
  isConnectable: boolean;
};

const JsonArtifactNode: React.FC<Props> = ({ data, isConnectable }) => {
  return (
    <Node
      icon={faPencil}
      data={data}
      isConnectable={isConnectable}
      defaultLabel="Parameter"
    />
  );
};

export default memo(JsonArtifactNode);
