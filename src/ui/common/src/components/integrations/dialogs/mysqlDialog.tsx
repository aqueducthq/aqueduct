import Box from '@mui/material/Box';
import React, { useEffect, useState } from 'react';

import { IntegrationConfig, MySqlConfig } from '../../../utils/integrations';
import { IntegrationTextInputField } from './dialog';

const Placeholders: MySqlConfig = {
  host: '127.0.0.1',
  port: '3306',
  database: 'aqueduct-db',
  username: 'aqueduct',
  password: '********',
};

type Props = {
  setDialogConfig: (config: IntegrationConfig) => void;
};

export const MysqlDialog: React.FC<Props> = ({ setDialogConfig }) => {
  const [host, setHost] = useState(null);
  const [port, setPort] = useState(null);
  const [database, setDatabase] = useState(null);
  const [username, setUsername] = useState(null);
  const [password, setPassword] = useState(null);

  useEffect(() => {
    const config: MySqlConfig = {
      host: host,
      port: port,
      database: database,
      username: username,
      password: password,
    };
    setDialogConfig(config);
  }, [host, port, database, username, password]);

  return (
    <Box sx={{ mt: 2 }}>
      <IntegrationTextInputField
        spellCheck={false}
        required={true}
        label="Host*"
        description="The hostname or IP address of the MySQL server."
        placeholder={Placeholders.host}
        onChange={(event) => setHost(event.target.value)}
        value={host}
      />

      <IntegrationTextInputField
        spellCheck={false}
        required={true}
        label="Port*"
        description="The port number of the MySQL server."
        placeholder={Placeholders.port}
        onChange={(event) => setPort(event.target.value)}
        value={port}
      />

      <IntegrationTextInputField
        spellCheck={false}
        required={true}
        label="Database*"
        description="The name of the specific database to connect to."
        placeholder={Placeholders.database}
        onChange={(event) => setDatabase(event.target.value)}
        value={database}
      />

      <IntegrationTextInputField
        spellCheck={false}
        required={true}
        label="Username*"
        description="The username of a user with access to the above database."
        placeholder={Placeholders.username}
        onChange={(event) => setUsername(event.target.value)}
        value={username}
      />

      <IntegrationTextInputField
        spellCheck={false}
        required={true}
        label="Password*"
        description="The password corresponding to the above username."
        placeholder={Placeholders.password}
        type="password"
        onChange={(event) => setPassword(event.target.value)}
        value={password}
      />
    </Box>
  );
};
