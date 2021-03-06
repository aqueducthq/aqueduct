import { faDatabase } from '@fortawesome/free-solid-svg-icons';
import React, { memo } from 'react';

import { ReactFlowNodeData } from '../../../utils/reactflow';
import Node from './Node';

type Props = {
  data: ReactFlowNodeData;
  isConnectable: boolean;
};

const DatabaseNode: React.FC<Props> = ({ data, isConnectable }) => {
  return (
    <Node
      icon={faDatabase}
      data={data}
      isConnectable={isConnectable}
      defaultLabel="Database"
    />
  );
};

export default memo(DatabaseNode);
